"""Доступ к базе данных StroyMir_KB (SQL Server через pyodbc)."""
from contextlib import contextmanager

import pyodbc

import config


@contextmanager
def connect():
    conn = pyodbc.connect(config.connection_string(), autocommit=False, timeout=5)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def query(sql, *params):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, *params)
        return _rows(cur)


def execute(sql, *params):
    with connect() as conn:
        conn.cursor().execute(sql, *params)


def _split(s):
    return [x.strip() for x in (s or "").split(";") if x.strip()]


# --------------------------------------------------------------- загрузка БЗ
def load_knowledge():
    """Всё, что нужно поисковому индексу, одним соединением."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id_tag, t.name, t.synonyms, t.definition, c.id_category, c.name AS category
            FROM kb.Tag AS t JOIN kb.Category AS c ON c.id_category = t.id_category""")
        concepts = [{"id": r["id_tag"], "name": r["name"], "synonyms": _split(r["synonyms"]),
                     "description": r["definition"] or "", "category": r["category"],
                     "category_id": r["id_category"]} for r in _rows(cur)]

        cur.execute("SELECT id_tag_from, relation_type, id_tag_to FROM kb.Relation")
        relations = [{"from": r[0], "type": r[1], "to": r[2]} for r in cur.fetchall()]

        cur.execute("""
            SELECT mt.id_material, mt.id_tag, t.name, mt.relevance
            FROM kb.MaterialTag AS mt JOIN kb.Tag AS t ON t.id_tag = mt.id_tag
            ORDER BY mt.relevance DESC""")
        tags_by_doc = {}
        for r in cur.fetchall():
            tags_by_doc.setdefault(r[0], []).append({"id": r[1], "name": r[2], "relevance": float(r[3])})

        cur.execute("SELECT * FROM kb.v_MaterialCard")
        docs = []
        for r in _rows(cur):
            docs.append({
                "id": r["id_material"], "title": r["title"], "summary": r["summary"] or "",
                "body": r["body"], "type": r["type_name"], "type_id": r["id_type"],
                "publisher": r["publisher_name"], "country": r["country_name"],
                "date": r["publish_date"], "views": r["views"],
                "tags": tags_by_doc.get(r["id_material"], []),
                "video": (r["video_platform"], r["video_url"], r["duration_sec"]) if r["video_url"] else None,
            })

        cur.execute("""
            SELECT pr.id_product AS id, pr.product_name AS name, c.category_name AS category,
                   mf.manufacturer_name AS manufacturer, MIN(b.base_price) AS price,
                   MIN(b.packaging_unit) AS unit
            FROM dbo.Product pr
            JOIN dbo.Category c ON c.id_category = pr.id_category
            JOIN dbo.Manufacturer mf ON mf.id_manufacturer = c.id_manufacturer
            LEFT JOIN dbo.Batch b ON b.id_product = pr.id_product
            GROUP BY pr.id_product, pr.product_name, c.category_name, mf.manufacturer_name""")
        products = _rows(cur)

        cur.execute("SELECT query_text, cnt FROM kb.fn_PopularQueries(50)")
        popular = [(r[0], r[1]) for r in cur.fetchall()]
    return docs, concepts, relations, products, popular


def content_types():
    return query("SELECT id_type, name FROM kb.ContentType ORDER BY id_type")


def tag_categories():
    return query("SELECT id_category, name FROM kb.Category ORDER BY id_category")


def publishers():
    return query("SELECT id_izdanie, name FROM kb.Publisher ORDER BY name")


def countries():
    return query("SELECT id_country, name FROM kb.Country ORDER BY name")


# ------------------------------------------------------------- статьи
def open_material(id_material):
    """Открытие статьи: процедура увеличивает счётчик и возвращает карточку."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("EXEC kb.usp_Material_View ?", id_material)
        rows = _rows(cur)
        if not rows:
            return None
        m = rows[0]
        cur.execute("""
            SELECT t.id_tag, t.name, mt.relevance, mt.position_in_results
            FROM kb.MaterialTag mt JOIN kb.Tag t ON t.id_tag = mt.id_tag
            WHERE mt.id_material = ? ORDER BY mt.relevance DESC""", id_material)
        m["tags"] = _rows(cur)
    return m


def material_for_edit(id_material):
    rows = query("""SELECT m.*, v.platform, v.url, v.duration_sec
                    FROM kb.Material m LEFT JOIN kb.VideoSource v ON v.id_material = m.id_material
                    WHERE m.id_material = ?""", id_material)
    if not rows:
        return None
    m = rows[0]
    m["tags"] = query("""SELECT t.name, mt.relevance FROM kb.MaterialTag mt
                         JOIN kb.Tag t ON t.id_tag = mt.id_tag WHERE mt.id_material = ?
                         ORDER BY mt.relevance DESC""", id_material)
    return m


def list_materials():
    return query("""SELECT id_material, title, type_name, publisher_name, publish_date, views
                    FROM kb.v_MaterialCard ORDER BY title""")


def save_material(data, tags, video):
    """data: title, summary, body, publish_date, id_izdanie, id_type, id_country, [id_material]
    tags: [(название тега, релевантность)], video: (платформа, ссылка, длительность) или None."""
    with connect() as conn:
        cur = conn.cursor()
        if data.get("id_material"):
            mid = int(data["id_material"])
            cur.execute("""UPDATE kb.Material SET title=?, summary=?, body=?, publish_date=?,
                           id_izdanie=?, id_type=?, id_country=? WHERE id_material=?""",
                        data["title"], data["summary"], data["body"], data["publish_date"],
                        data["id_izdanie"], data["id_type"], data["id_country"], mid)
            cur.execute("DELETE FROM kb.MaterialTag WHERE id_material = ?", mid)
            cur.execute("DELETE FROM kb.VideoSource WHERE id_material = ?", mid)
        else:
            cur.execute("""INSERT INTO kb.Material (title, summary, body, publish_date, id_izdanie, id_type, id_country)
                           OUTPUT inserted.id_material VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        data["title"], data["summary"], data["body"], data["publish_date"],
                        data["id_izdanie"], data["id_type"], data["id_country"])
            mid = cur.fetchone()[0]
        for name, rel in tags:
            cur.execute("""INSERT INTO kb.MaterialTag (id_material, id_tag, relevance)
                           SELECT ?, id_tag, ? FROM kb.Tag WHERE name = ?""", mid, rel, name)
        if video:
            cur.execute("INSERT INTO kb.VideoSource (id_material, platform, url, duration_sec) VALUES (?, ?, ?, ?)",
                        mid, *video)
        cur.execute("EXEC kb.usp_RecalcRanks")
    return mid


def delete_material(id_material):
    execute("DELETE FROM kb.Material WHERE id_material = ?", id_material)


# ------------------------------------------------------------- понятия
def concept(id_tag):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT t.*, c.name AS category FROM kb.Tag t
                       JOIN kb.Category c ON c.id_category = t.id_category WHERE t.id_tag = ?""", id_tag)
        rows = _rows(cur)
        if not rows:
            return None
        c = rows[0]
        c["synonyms_list"] = _split(c["synonyms"])
        cur.execute("SELECT * FROM kb.fn_ConceptNeighbors(?) ORDER BY relation_type, name", id_tag)
        c["neighbors"] = _rows(cur)
        cur.execute("SELECT * FROM kb.fn_ConceptAncestors(?) ORDER BY lvl", id_tag)
        c["ancestors"] = _rows(cur)
        cur.execute("SELECT * FROM kb.fn_InheritedFacts(?) ORDER BY lvl, relation_type, name", id_tag)
        c["inherited"] = _rows(cur)
        cur.execute("""SELECT m.id_material, m.title, mt.relevance, mt.position_in_results
                       FROM kb.MaterialTag mt JOIN kb.Material m ON m.id_material = mt.id_material
                       WHERE mt.id_tag = ? ORDER BY mt.position_in_results""", id_tag)
        c["materials"] = _rows(cur)
    return c


def list_concepts():
    return query("""SELECT t.id_tag, t.name, t.synonyms, t.definition, c.name AS category, t.id_category,
                           (SELECT COUNT(*) FROM kb.MaterialTag mt WHERE mt.id_tag = t.id_tag) AS materials,
                           (SELECT COUNT(*) FROM kb.Relation r
                            WHERE r.id_tag_from = t.id_tag OR r.id_tag_to = t.id_tag) AS relations
                    FROM kb.Tag t JOIN kb.Category c ON c.id_category = t.id_category
                    ORDER BY c.id_category, t.name""")


def save_concept(id_tag, id_category, name, synonyms, definition):
    if id_tag:
        execute("UPDATE kb.Tag SET id_category=?, name=?, synonyms=?, definition=? WHERE id_tag=?",
                id_category, name, synonyms, definition, id_tag)
    else:
        execute("INSERT INTO kb.Tag (id_category, name, synonyms, definition) VALUES (?, ?, ?, ?)",
                id_category, name, synonyms, definition)


def add_relation(src, rel_type, dst):
    execute("""INSERT INTO kb.Relation (id_tag_from, relation_type, id_tag_to)
               SELECT f.id_tag, ?, t.id_tag FROM kb.Tag f, kb.Tag t WHERE f.name = ? AND t.name = ?""",
            rel_type, src, dst)


def delete_relation(id_relation):
    execute("DELETE FROM kb.Relation WHERE id_relation = ?", id_relation)


def relations_of(id_tag):
    return query("""SELECT r.id_relation, f.name AS src, r.relation_type, t.name AS dst
                    FROM kb.Relation r JOIN kb.Tag f ON f.id_tag = r.id_tag_from
                    JOIN kb.Tag t ON t.id_tag = r.id_tag_to
                    WHERE r.id_tag_from = ? OR r.id_tag_to = ? ORDER BY r.relation_type""", id_tag, id_tag)


# ------------------------------------------------------------- экспертная система
def expert_knowledge():
    questions = query("SELECT * FROM kb.Question ORDER BY sort_order")
    for qn in questions:
        qn["options_list"] = _split(qn["options"])
        qn["cond_values_list"] = _split(qn["cond_values"])
    rules = query("""SELECT r.id_rule, r.code, r.then_kind, r.then_attribute, r.then_value,
                            r.id_tag, t.name AS tag_name, r.cf, r.explanation
                     FROM kb.[Rule] r LEFT JOIN kb.Tag t ON t.id_tag = r.id_tag ORDER BY r.id_rule""")
    conds = query("SELECT id_rule, attribute, value FROM kb.RuleCondition ORDER BY id_condition")
    by_rule = {}
    for c in conds:
        by_rule.setdefault(c["id_rule"], []).append((c["attribute"], c["value"]))
    for r in rules:
        r["conditions"] = by_rule.get(r["id_rule"], [])
        r["cf"] = float(r["cf"])
    return questions, rules


# ------------------------------------------------------------- журнал и статистика
def log_search(text, kind, words, results, elapsed, corrected):
    execute("EXEC kb.usp_SearchLog_Add ?, ?, ?, ?, ?, ?", text, kind, words, results, elapsed, corrected)


def search_stats():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("EXEC kb.usp_SearchStats")
        by_kind = _rows(cur)
        cur.execute("SELECT TOP 15 query_text, cnt FROM kb.fn_PopularQueries(15)")
        popular = _rows(cur)
        cur.execute("""SELECT TOP 15 query_text, MAX(created_at) AS last_at, COUNT(*) AS cnt
                       FROM kb.SearchLog WHERE results_count = 0
                       GROUP BY query_text ORDER BY MAX(created_at) DESC""")
        empty = _rows(cur)
        cur.execute("""SELECT TOP 20 query_text, query_kind, words_count, results_count, elapsed_ms,
                              corrected, created_at FROM kb.SearchLog ORDER BY id_log DESC""")
        recent = _rows(cur)
        cur.execute("""SELECT TOP 10 title, views, id_material FROM kb.Material
                       WHERE views > 0 ORDER BY views DESC""")
        top_materials = _rows(cur)
    return {"by_kind": by_kind, "popular": popular, "empty": empty, "recent": recent,
            "top_materials": top_materials}


def catalog():
    return query("SELECT * FROM dbo.v_ProductCatalog ORDER BY category_name, product_name")
