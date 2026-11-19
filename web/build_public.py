"""Build the portable public site from the original Python knowledge base.

Usage: python build_public.py --source W:/project/stroy_kb
When copied to web/, the parent directory is used automatically.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sqlite3
import sys

HERE = Path(__file__).resolve().parent


def catalog(source):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE Manufacturer (id_manufacturer INTEGER PRIMARY KEY, manufacturer_name, city, foundation_year);
        CREATE TABLE Category (id_category INTEGER PRIMARY KEY, id_manufacturer, category_name, standard_year);
        CREATE TABLE Product (id_product INTEGER PRIMARY KEY, id_category, product_name, packaging_type, material_class, shelf_life_months);
        CREATE TABLE RawMaterial (id_raw_material INTEGER PRIMARY KEY, raw_material_code, raw_material_type, density, thermal_conductivity, compressive_strength, service_life_years);
        CREATE TABLE Batch (id_batch INTEGER PRIMARY KEY, id_product, id_raw_material, batch_name, delivery_type, packaging_unit, base_price);
        CREATE TABLE Delivery (id_delivery INTEGER PRIMARY KEY, id_batch, delivery_date, object_name, quantity, delivery_price);
    """)
    sql = (source / "data/catalog.sql").read_text(encoding="utf-8-sig")
    sql = re.sub(r"^GO\s*$", "", sql, flags=re.M)
    sql = re.sub(r"\bN'", "'", sql).replace("dbo.", "")
    sql = sql.replace("AS v(product_name, code, batch_name, delivery_type, unit, price)", "AS v")
    for i, name in enumerate(["product_name", "code", "batch_name", "delivery_type", "unit", "price"], 1):
        sql = sql.replace("v." + name, "v.column" + str(i))
    conn.executescript(sql)
    rows = conn.execute("""
        SELECT pr.id_product AS id, pr.product_name AS name, c.category_name AS category,
               mf.manufacturer_name AS manufacturer, mf.city, pr.material_class,
               b.base_price AS price, b.packaging_unit AS unit,
               rm.density, rm.thermal_conductivity, rm.compressive_strength, rm.service_life_years
        FROM Product pr JOIN Category c ON c.id_category=pr.id_category
        JOIN Manufacturer mf ON mf.id_manufacturer=c.id_manufacturer
        LEFT JOIN Batch b ON b.id_product=pr.id_product
        LEFT JOIN RawMaterial rm ON rm.id_raw_material=b.id_raw_material
        ORDER BY pr.id_product
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build(source, site_url='http://dusovstroimir.mooo.com/'):
    sys.path.insert(0, str(source))
    from data import knowledge as K
    from search.engine import KnowledgeIndex, INTENTS, INTENT_TRIGGER_STEMS, RELATION_LABELS
    from search.text import STOPWORDS, QUESTION_WORDS, stem
    from search import stemmer
    from expert import infer
    from data.enrichment import guide_for, collections

    categories = [{"id": i, "name": n, "description": d}
                  for i, (n, d) in enumerate(K.CATEGORIES, 1)]
    cat_ids = {c["name"]: c["id"] for c in categories}
    type_ids = {n: i for i, (n, _) in enumerate(K.CONTENT_TYPES, 1)}
    concepts = [{"id": i, "name": n, "category": cat, "category_id": cat_ids[cat],
                 "synonyms": syn, "description": desc}
                for i, (n, cat, syn, desc) in enumerate(K.CONCEPTS, 1)]
    concept_ids = {c["name"]: c["id"] for c in concepts}
    relations = [{"from": concept_ids[a], "to": concept_ids[b], "type": typ}
                 for a, typ, b in K.RELATIONS]
    docs = [{"id": i, "title": title, "summary": summary, "body": body, "type": typ,
             "type_id": type_ids[typ], "publisher": pub, "country": country, "date": date,
             "tags": [{"id": concept_ids[t], "name": t, "relevance": r} for t, r in tags],
             "video": video}
            for i, (title, typ, pub, country, date, tags, summary, body, video) in enumerate(K.ARTICLES, 1)]
    for doc,article in zip(docs,K.ARTICLES):
        doc["guide"] = guide_for(article)
    products = catalog(source)
    ix = KnowledgeIndex(docs, concepts, relations, products)
    questions = [{"attribute": a, "question_text": q, "options_list": opts,
                  "cond_attribute": cond[0] if cond else None,
                  "cond_values_list": cond[1] if cond else []}
                 for a, q, opts, cond in K.QUESTIONS]
    rules = [{"code": code, "conditions": conditions, "then_kind": then[0],
              "then_attribute": then[1] if then[0] == "fact" else None,
              "then_value": then[2] if then[0] == "fact" else None,
              "id_tag": concept_ids[then[1]] if then[0] == "tag" else None,
              "tag_name": then[1] if then[0] == "tag" else None, "cf": cf, "explanation": explanation}
             for code, conditions, then, cf, explanation in K.RULES]
    payload = {
        "documents": docs, "concepts": concepts, "relations": relations, "products": products,
        "collections": collections(K.ARTICLES), "categories": categories, "types": [{"id": i, "name": n} for n, i in type_ids.items()],
        "questions": questions, "rules": rules, "labels": RELATION_LABELS,
        "postings": ix.postings, "positions": ix.positions, "field_len": ix.field_len,
        "avg_len": ix.avg_len, "idf": ix.idf, "vocabulary": ix.speller.freq,
        "phrases": [[list(k), v] for k, v in ix.concept_phrases.items()],
        "stopwords": sorted(STOPWORDS), "question_words": sorted(QUESTION_WORDS),
        "intent_stems": sorted(INTENT_TRIGGER_STEMS),
        "intents": [[name, rx.pattern, rel, title] for name, rx, rel, title in INTENTS],
        "suffixes": {name: getattr(stemmer, name) for name in [
            "PERFECTIVE_GERUND_1", "PERFECTIVE_GERUND_2", "REFLEXIVE", "ADJECTIVE",
            "PARTICIPLE_1", "PARTICIPLE_2", "VERB_1", "VERB_2", "NOUN", "SUPERLATIVE", "DERIVATIONAL"]},
        "stats": {k: v for k, v in ix.stats().items() if k != "build_ms"},
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    source_bytes = b"".join(p.read_bytes() for p in sorted((HERE / "src").iterdir()) if p.is_file())
    version = hashlib.sha256(encoded.encode() + source_bytes).hexdigest()[:12]
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    for item in (HERE / "src").iterdir():
        if item.is_file():
            shutil.copy2(item, dist / item.name)
    shutil.copytree(source / "static/media", dist / "media", dirs_exist_ok=True)
    (dist / "knowledge.json").write_text(encoded, encoding="utf-8")
    sw = dist / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8").replace("__BUILD__", version), encoding="utf-8")
    (dist / ".nojekyll").touch()
    from seo import render_static_site
    render_static_site(dist, payload, site_url)

    sys.path.insert(0, str(source / "docs"))
    from evaluate import GOLD
    queries = [q for group in GOLD.values() for q in group]
    queries += ["", "абырвалг квазистроение", "кирпичами", "что такое бетон", "ГКЛВ", "бетон " * 20]
    expected = []
    for q in queries:
        result = ix.search(q)
        expected.append({"q": q, "ids": [r["doc"]["id"] for r in result["results"]],
                         "corrected": result["query"].corrected, "concepts": result["query"].concepts,
                         "answer": result["answer"]["text_html"] if result["answer"] else None})
    rng = random.Random(42)
    scenarios = []
    for _ in range(150):
        answers = {q["attribute"]: rng.choice(q["options_list"]) for q in questions}
        result = infer(rules, answers)
        scenarios.append({"answers": answers, "recommended": [[r["id_tag"], r["cf"]] for r in result["recommended"]],
                          "rejected": [[r["id_tag"], r["cf"]] for r in result["rejected"]],
                          "facts": result["facts"], "trace": [r["rule"]["code"] for r in result["trace"]]})
    fixtures = {"queries": expected, "expert": scenarios,
                "stems": {w: stem(w) for w in ix.speller.freq}}
    (HERE / "tests/parity.json").write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")
    print(f"Built dusovstroimir: {len(docs)} articles, {len(concepts)} concepts, {len(rules)} rules, "
          f"{len(products)} catalog entries; knowledge payload {len(encoded.encode()):,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=HERE.parent)
    parser.add_argument("--site-url", default='http://dusovstroimir.mooo.com/')
    args = parser.parse_args()
    build(args.source.resolve(), args.site_url)
