"""
Генерация SQL-скрипта наполнения базы знаний и развёртывание БД.

    py seed.py              — сгенерировать sql/02_data.sql
    py seed.py --deploy     — сгенерировать и выполнить скрипты 01–03 через sqlcmd
"""
import argparse
import json
from data.enrichment import guide_for
from data.review_model import DEFINITIONS,property_records,rule_note
from web.build_public import catalog
import subprocess
import sys
from pathlib import Path

import config
from data import knowledge as K

ROOT = Path(__file__).parent
SQL_DIR = ROOT / "sql"


def q(value):
    """Строковый литерал T-SQL (или NULL)."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "N'" + str(value).replace("'", "''") + "'"


def values_insert(table, columns, rows, chunk=50):
    out = []
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        out.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n    "
                   + ",\n    ".join("(" + ", ".join(r) + ")" for r in part) + ";")
    return "\n".join(out) + "\nGO\n"


def generate():
    parts = [
        "/* ============================================================\n"
        "   КУРСОВОЙ ПРОЕКТ «СтройМир» — скрипт 2 из 3\n"
        "   Наполнение каталога и базы знаний.\n"
        "   ФАЙЛ СГЕНЕРИРОВАН seed.py из data/knowledge.py — не редактируйте вручную.\n"
        "   ============================================================ */",
        "USE StroyMir_KB_Review_20261121;\nGO\n",
        (ROOT / "data" / "catalog.sql").read_text(encoding="utf-8"),
        "\n/* ===================== БАЗА ЗНАНИЙ ===================== */\n",
    ]

    parts.append(values_insert("kb.Country", ["name", "iso_code"],
                               [[q(n), q(c)] for n, c in K.COUNTRIES]))
    parts.append(
        "INSERT INTO kb.Publisher (name, id_country, site)\nSELECT v.name, c.id_country, v.site\nFROM (VALUES\n    "
        + ",\n    ".join(f"({q(n)}, {q(c)}, {q(s)})" for n, c, s in K.PUBLISHERS)
        + "\n) AS v(name, country, site)\nJOIN kb.Country AS c ON c.name = v.country;\nGO\n")
    parts.append(values_insert("kb.ContentType", ["name", "description"],
                               [[q(n), q(d)] for n, d in K.CONTENT_TYPES]))
    parts.append(values_insert("kb.Category", ["name", "description"],
                               [[q(n), q(d)] for n, d in K.CATEGORIES]))

    parts.append(
        "INSERT INTO kb.Tag (id_category, name, synonyms, definition)\n"
        "SELECT c.id_category, v.name, v.synonyms, v.definition\nFROM (VALUES\n    "
        + ",\n    ".join(f"({q(n)}, {q(cat)}, {q('; '.join(syn))}, {q(d)})" for n, cat, syn, d in K.CONCEPTS)
        + "\n) AS v(name, category, synonyms, definition)\nJOIN kb.Category AS c ON c.name = v.category;\nGO\n")

    parts.append(
        "INSERT INTO kb.Relation (id_tag_from, relation_type, id_tag_to)\n"
        "SELECT f.id_tag, v.rel, t.id_tag\nFROM (VALUES\n    "
        + ",\n    ".join(f"({q(a)}, {q(r)}, {q(b)})" for a, r, b in K.RELATIONS)
        + "\n) AS v(src, rel, dst)\nJOIN kb.Tag AS f ON f.name = v.src\nJOIN kb.Tag AS t ON t.name = v.dst;\nGO\n")

    for title, typ, pub, country, date, tags, summary, body, video in K.ARTICLES:
        parts.append(
            "INSERT INTO kb.Material (title, summary, body, publish_date, id_izdanie, id_type, id_country)\n"
            f"SELECT {q(title)}, {q(summary)}, {q(body)}, '{date}', p.id_izdanie, ct.id_type, c.id_country\n"
            f"FROM kb.Publisher AS p, kb.ContentType AS ct, kb.Country AS c\n"
            f"WHERE p.name = {q(pub)} AND ct.name = {q(typ)} AND c.name = {q(country)};")
        parts.append(
            "INSERT INTO kb.MaterialTag (id_material, id_tag, relevance)\n"
            "SELECT m.id_material, t.id_tag, v.rel\nFROM (VALUES "
            + ", ".join(f"({q(t)}, {r})" for t, r in tags)
            + f") AS v(tag, rel)\nJOIN kb.Tag AS t ON t.name = v.tag\n"
            f"JOIN kb.Material AS m ON m.title = {q(title)};")
        if video:
            platform, url, dur = video
            parts.append(
                "INSERT INTO kb.VideoSource (id_material, platform, url, duration_sec)\n"
                f"SELECT id_material, {q(platform)}, {q(url)}, {dur} FROM kb.Material WHERE title = {q(title)};")
        parts.append("GO\n")

    parts.append(values_insert(
        "kb.Question", ["attribute", "question_text", "options", "cond_attribute", "cond_values", "sort_order"],
        [[q(a), q(t), q("; ".join(opts)), q(cond[0] if cond else None),
          q("; ".join(cond[1]) if cond else None), str(i + 1)]
         for i, (a, t, opts, cond) in enumerate(K.QUESTIONS)]))

    for code, conds, then, cf, expl in K.RULES:
        if then[0] == "fact":
            parts.append("INSERT INTO kb.[Rule] (code, then_kind, then_attribute, then_value, cf, explanation)\n"
                         f"VALUES ('{code}', 'fact', {q(then[1])}, {q(then[2])}, {cf}, {q(expl)});")
        else:
            parts.append("INSERT INTO kb.[Rule] (code, then_kind, id_tag, cf, explanation)\n"
                         f"SELECT '{code}', 'tag', id_tag, {cf}, {q(expl)} FROM kb.Tag WHERE name = {q(then[1])};")
        parts.append("INSERT INTO kb.RuleCondition (id_rule, attribute, value)\n"
                     "SELECT r.id_rule, v.a, v.v FROM kb.[Rule] AS r CROSS JOIN (VALUES "
                     + ", ".join(f"({q(a)}, {q(v)})" for a, v in conds)
                     + f") AS v(a, v) WHERE r.code = '{code}';")
    parts.append("GO\n")

    for article in K.ARTICLES:
        encoded=json.dumps(guide_for(article),ensure_ascii=False)
        parts.append("INSERT kb.ArticleGuide(id_material,guide_json) SELECT id_material,"+q(encoded)+" FROM kb.Material WHERE title="+q(article[0])+";\nGO\n")
    parts.append(values_insert('kb.PropertyDefinition',['code','name','unit'],[[q(code),q(name),q(unit)] for code,(name,unit) in DEFINITIONS.items()]))
    for rule in K.RULES:
        parts.append("INSERT kb.RuleProvenance(code,notes) VALUES("+q(rule[0])+","+q(json.dumps(rule_note(rule),ensure_ascii=False))+");\nGO\n")
    for p in property_records(catalog(ROOT)):
        parts.append("INSERT kb.MaterialProperty(id_product,id_tag,property_code,numeric_value,conditions,source_kind,source_url) SELECT "+q(p['product_id'])+",id_tag,"+','.join(q(p[key]) for key in ['attribute','value','conditions','source_kind','source_url'])+" FROM kb.Tag WHERE name="+q(p['concept'])+";\nGO\n")
    parts.append("EXEC kb.usp_RecalcRanks;\nGO\n")
    parts.append(
        "/* Контроль наполнения */\n"
        "SELECT 'Статьи' AS obj, COUNT(*) AS cnt FROM kb.Material UNION ALL\n"
        "SELECT 'Понятия', COUNT(*) FROM kb.Tag UNION ALL\n"
        "SELECT 'Связи', COUNT(*) FROM kb.Relation UNION ALL\n"
        "SELECT 'Теги статей', COUNT(*) FROM kb.MaterialTag UNION ALL\n"
        "SELECT 'Правила', COUNT(*) FROM kb.[Rule] UNION ALL\n"
        "SELECT 'Продукция', COUNT(*) FROM dbo.Product;\nGO\n")

    out = SQL_DIR / "02_data.sql"
    out.write_text("\n".join(parts), encoding="utf-8-sig")
    print(f"Сгенерирован {out}")
    return out


def run_sql(path):
    print(f"Выполняется {path.name} ...")
    cmd = ["sqlcmd", "-S", config.SQL_SERVER, "-b", "-f", "65001", "-i", str(path)]
    cmd += ["-U", config.SQL_USER, "-P", config.SQL_PASSWORD] if config.SQL_USER else ["-E"]
    if config.SQL_TRUST_CERT:
        cmd.append("-C")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(res.stdout[-3000:])
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise SystemExit(f"Ошибка выполнения {path.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="создать БД и загрузить данные")
    args = ap.parse_args()
    generate()
    if args.deploy:
        # Процедуры (03) создаются до загрузки данных, т.к. 02 вызывает usp_RecalcRanks
        for name in ("01_schema.sql", "03_procedures.sql", "02_data.sql"):
            run_sql(SQL_DIR / name)
        print("База данных StroyMir_KB развёрнута.")
