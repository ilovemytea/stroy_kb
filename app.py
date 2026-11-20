"""
Веб-приложение базы знаний «СтройМир».

Запуск:  py app.py   →  http://localhost:5000
"""
import json
from pathlib import Path
import threading
import time
from datetime import date
from functools import wraps

import pyodbc
from flask import (Flask, abort, flash, jsonify, redirect, render_template, request, session,
                   url_for)

# PyCharm's Run button starts this file as __main__; use private local settings.
if __name__ == '__main__':
    from local_setup import configure_local
    _local_settings_path = configure_local()
    if _local_settings_path:
        print('Локальные настройки: ' + _local_settings_path.name + ' (не публикуются в Git).')

import config
import db
import expert
from search.engine import MAX_QUERY_WORDS, RELATION_LABELS, KnowledgeIndex

if not config.ADMIN_PASSWORD or not config.SECRET_KEY:
    raise RuntimeError(
        "Перед запуском задайте STROYMIR_ADMIN_PASSWORD и STROYMIR_SECRET_KEY "
        "в переменных окружения (см. README.md)."
    )

if '_Review_' not in config.SQL_DATABASE:
    raise RuntimeError('Экспериментальная копия не подключается к рабочей базе. Выберите отдельную базу _Review_.')

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

_index = None
_index_lock = threading.Lock()


def get_index() -> KnowledgeIndex:
    global _index
    if _index is None:
        reload_index()
    return _index


def reload_index():
    """Перестроение инвертированного индекса после изменения базы знаний."""
    global _index
    with _index_lock:
        docs, concepts, relations, products, popular = db.load_knowledge()
        _index = KnowledgeIndex(docs, concepts, relations, products, popular)


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"MAX_QUERY_WORDS": MAX_QUERY_WORDS, "is_admin": session.get("admin", False),
            "REL_LABELS": RELATION_LABELS}


@app.template_filter("duration")
def duration(sec):
    if not sec:
        return ""
    return f"{sec // 60}:{sec % 60:02d}"


# ------------------------------------------------------------------ поиск
EXAMPLES = [
    ("слово", "минвата"),
    ("слово", "гипсакартон"),
    ("словосочетание", "кирпич для фундамента"),
    ("словосочетание", "чем заменить газобетон"),
    ("предложение", "какой утеплитель выбрать для бани чтобы он не горел"),
    ("предложение", "какой бетон нужен для ленточного фундамента частного дома из газобетона"),
]


@app.route("/")
def home():
    ix = get_index()
    return render_template("home.html", stats=ix.stats(), examples=EXAMPLES,
                           categories=db.tag_categories(),
                           concepts=sorted(ix.concepts.values(), key=lambda c: c["name"]))


@app.route("/guides")
def guides():
    from data import knowledge as K
    from data.enrichment import guide_for
    known = {a[0]:guide_for(a) for a in K.ARTICLES}
    articles=[dict(d,guide=known.get(d['title'])) for d in get_index().docs.values()]
    return render_template('guides.html',articles=sorted(articles,key=lambda d:d['id'],reverse=True))


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("home"))
    type_id = request.args.get("type", type=int)
    cat_id = request.args.get("cat", type=int)
    ix = get_index()
    res = ix.search(q, type_id=type_id, category_id=cat_id)
    pq = res["query"]
    if not type_id and not cat_id:
        try:
            db.log_search(q, pq.kind, len(pq.words), res["total"], res["took_ms"], pq.corrected)
        except Exception as e:      # журнал не должен ломать поиск
            app.logger.warning("Журнал поиска недоступен: %s", e)
    return render_template("search.html", q=q, res=res, pq=pq, type_id=type_id, cat_id=cat_id,
                           types=db.content_types(), categories=db.tag_categories())


@app.route("/api/suggest")
def api_suggest():
    return jsonify(get_index().suggest(request.args.get("q", "")))


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    res = get_index().search(q, limit=request.args.get("limit", 10, type=int))
    pq = res["query"]
    return jsonify({
        "query": q, "kind": pq.kind, "words": len(pq.words), "truncated": pq.truncated,
        "corrected": pq.corrected, "intent": pq.intent[0] if pq.intent else None,
        "concepts": [get_index().concepts[c]["name"] for c in pq.concepts],
        "terms": [{"stem": t.stem, "weight": t.weight, "origin": t.origin, "label": t.label}
                  for t in pq.terms],
        "total": res["total"], "took_ms": res["took_ms"],
        "results": [{"id": r["doc"]["id"], "title": r["doc"]["title"], "score": r["score"],
                     "explain": r["explain"]} for r in res["results"]],
    })


# ------------------------------------------------------------------ статьи и понятия
@app.route("/material/<int:mid>")
def material(mid):
    m = db.open_material(mid)
    if not m:
        abort(404)
    hl = request.args.get("hl", "")
    body_html = None
    if hl:
        ix = get_index()
        stems = {t.stem for t in ix.parse(hl).terms if t.origin != "intent"}
        body_html = [ix.highlight(p, stems) for p in m["body"].split("\n") if p.strip()]
    return render_template("material.html", m=m, body_html=body_html, hl=hl)


@app.route("/concept/<int:cid>")
def concept(cid):
    c = db.concept(cid)
    if not c:
        abort(404)
    groups = {}
    out_replace={n['id_tag'] for n in c['neighbors'] if n['relation_type']=='заменяет' and n['direction']=='out'}
    in_replace={n['id_tag'] for n in c['neighbors'] if n['relation_type']=='заменяет' and n['direction']=='in'}
    mutual=out_replace & in_replace
    for n in c["neighbors"]:
        labels = RELATION_LABELS.get(n["relation_type"], (n["relation_type"], n["relation_type"]))
        label = labels[0] if n["direction"] == "out" else labels[1]
        if n['relation_type']=='заменяет' and n['id_tag'] in mutual:
            if n['direction']=='in':continue
            label='Взаимная замена (зависит от условий)'
        groups.setdefault(label, []).append(n)
    return render_template("concept.html", c=c, groups=groups)


@app.route("/concepts")
def concepts():
    rows = db.list_concepts()
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    return render_template("concepts.html", by_cat=by_cat)


@app.route("/graph")
def graph():
    return render_template("graph.html", focus=request.args.get("focus", type=int))


@app.route("/api/graph")
def api_graph():
    ix = get_index()
    return jsonify({
        "nodes": [{"id": c["id"], "name": c["name"], "category": c["category"]} for c in ix.concepts.values()],
        "links": [{"source": r["from"], "target": r["to"], "type": r["type"]} for r in ix.relations],
    })


# ------------------------------------------------------------------ экспертная система
@app.route("/expert", methods=["GET", "POST"])
def expert_view():
    questions, rules = db.expert_knowledge()
    # Ответы принимаются из формы (POST) или из адреса (GET) — так результат подбора можно открыть ссылкой.
    src = request.form if request.method == "POST" else request.args
    answers = {q["attribute"]: src.get(q["attribute"], "") for q in questions}
    result = None
    if answers.get("element"):
        visible = expert.visible_questions(questions, answers)
        used = {q["attribute"]: answers[q["attribute"]] for q in visible if answers[q["attribute"]]}
        result = expert.infer(rules, used)
        result["answers"] = used
    labels = {q["attribute"]: q["question_text"] for q in questions}
    return render_template("expert.html", questions=questions, answers=answers, result=result,
                           labels=labels, rules_count=len(rules))


@app.route("/expert/rules")
def expert_rules():
    questions, rules = db.expert_knowledge()
    return render_template("rules.html", rules=rules, questions=questions)


# ------------------------------------------------------------------ каталог и статистика
@app.route("/catalog")
def catalog():
    from data.review_model import CATALOG_ISSUES
    rows=db.catalog()
    for row in rows:
        row['review_issue']=CATALOG_ISSUES.get(row.get('id_product'))
        if row['product_name']=='Минеральная вата фасадная 100 кг/м3':row['review_issue']=CATALOG_ISSUES[15]
    return render_template("catalog.html", rows=rows)


BENCH_QUERIES = [
    "газобетон", "минвата", "гипсакартон", "ГКЛВ", "кровля",
    "кирпич для фундамента", "чем заменить газобетон", "утепление фасада минватой",
    "плитка в ванной", "из чего делают силикатный кирпич",
    "какой утеплитель выбрать для бани чтобы он не горел",
    "какой бетон нужен для ленточного фундамента частного дома из газобетона",
    "можно ли использовать гипсовую штукатурку в ванной комнате",
    "чем отличается керамогранит от обычной керамической плитки для пола на кухне",
    "какую тротуарную плитку выбрать для парковки автомобиля во дворе частного дома",
]


@app.route("/stats")
def stats():
    ix = get_index()
    bench = None
    if request.args.get("bench"):
        bench = []
        for q in BENCH_QUERIES:
            times = []
            for _ in range(20):
                t0 = time.perf_counter()
                r = ix.search(q)
                times.append((time.perf_counter() - t0) * 1000)
            times.sort()
            bench.append({"q": q, "kind": r["query"].kind, "words": len(r["query"].words),
                          "total": r["total"], "median": round(times[len(times) // 2], 2),
                          "max": round(times[-1], 2),
                          "top": r["results"][0]["doc"]["title"] if r["results"] else "—"})
    from docs.render_research import research_fragment
    path=Path(__file__).parent/'docs/research-results.json'
    research=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    return render_template("stats.html", engine=ix.stats(), s=db.search_stats(), bench=bench,research_html=research_fragment(research))


# ------------------------------------------------------------------ администрирование
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == config.ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("admin"))
        flash("Неверный пароль", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", materials=db.list_materials(), concepts=db.list_concepts())


def _parse_tags(text):
    tags = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, rel = line.partition("|")
        try:
            r = min(1.0, max(0.0, float(rel.replace(",", ".")))) if rel.strip() else 0.5
        except ValueError:
            r = 0.5
        tags.append((name.strip(), r))
    return tags


@app.route("/admin/material/new", methods=["GET", "POST"])
@app.route("/admin/material/<int:mid>", methods=["GET", "POST"])
@admin_required
def admin_material(mid=None):
    if request.method == "POST":
        f = request.form
        if f.get("delete") and mid:
            db.delete_material(mid)
            reload_index()
            flash("Статья удалена", "ok")
            return redirect(url_for("admin"))
        data = {
            "id_material": mid, "title": f["title"].strip(), "summary": f.get("summary", "").strip(),
            "body": f["body"].strip(), "publish_date": f.get("publish_date") or date.today().isoformat(),
            "id_izdanie": int(f["id_izdanie"]), "id_type": int(f["id_type"]),
            "id_country": int(f["id_country"]) if f.get("id_country") else None,
        }
        video = None
        if f.get("video_url", "").strip():
            dur = f.get("video_duration", "").strip()
            video = (f.get("video_platform") or "YouTube", f["video_url"].strip(), int(dur) if dur.isdigit() else None)
        try:
            new_id = db.save_material(data, _parse_tags(f.get("tags", "")), video)
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "error")
            m = dict(data, tags=[{"name": n, "relevance": r} for n, r in _parse_tags(f.get("tags", ""))])
            return render_template("admin_material.html", m=m, **_ref_lists())
        reload_index()
        flash("Статья сохранена, поисковый индекс перестроен", "ok")
        return redirect(url_for("admin_material", mid=new_id))
    m = db.material_for_edit(mid) if mid else None
    if mid and not m:
        abort(404)
    return render_template("admin_material.html", m=m, **_ref_lists())


def _ref_lists():
    return {"types": db.content_types(), "publishers": db.publishers(), "countries": db.countries(),
            "all_concepts": [c["name"] for c in db.list_concepts()]}


@app.route("/admin/concept/new", methods=["GET", "POST"])
@app.route("/admin/concept/<int:cid>", methods=["GET", "POST"])
@admin_required
def admin_concept(cid=None):
    if request.method == "POST":
        f = request.form
        try:
            if f.get("action") == "add_relation":
                db.add_relation(f["src"], f["relation_type"], f["dst"])
                flash("Связь добавлена", "ok")
            elif f.get("action") == "del_relation":
                db.delete_relation(int(f["id_relation"]))
                flash("Связь удалена", "ok")
            else:
                db.save_concept(cid, int(f["id_category"]), f["name"].strip(),
                                f.get("synonyms", "").strip(), f.get("definition", "").strip())
                flash("Понятие сохранено", "ok")
                if not cid:
                    reload_index()
                    return redirect(url_for("admin"))
        except Exception as e:
            flash(f"Ошибка: {e}", "error")
        reload_index()
        return redirect(request.url)
    c = db.concept(cid) if cid else None
    if cid and not c:
        abort(404)
    return render_template("admin_concept.html", c=c, categories=db.tag_categories(),
                           relations=db.relations_of(cid) if cid else [],
                           all_concepts=[x["name"] for x in db.list_concepts()],
                           rel_types=list(RELATION_LABELS))


@app.route("/admin/reindex", methods=["POST"])
@admin_required
def admin_reindex():
    reload_index()
    flash(f"Индекс перестроен за {get_index().build_ms:.1f} мс", "ok")
    return redirect(url_for("admin"))


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", title="Страница не найдена",
                           message="Такой страницы нет в базе знаний."), 404


@app.errorhandler(pyodbc.Error)
def db_error(e):
    return render_template("error.html", title="Нет связи с базой данных",
                           message="Проверьте, что SQL Server запущен и база StroyMir_KB развёрнута "
                                   "(py seed.py --deploy).", detail=str(e)), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.PORT, debug=False)
