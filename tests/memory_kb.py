"""Сборка индекса прямо из data/knowledge.py — для тестов без SQL Server."""
from data import knowledge as K
from search.engine import KnowledgeIndex


def build_memory_index(no_synonyms=False):
    cat_id = {name: i + 1 for i, (name, _) in enumerate(K.CATEGORIES)}
    cid = {c[0]: i + 1 for i, c in enumerate(K.CONCEPTS)}
    type_id = {name: i + 1 for i, (name, _) in enumerate(K.CONTENT_TYPES)}
    concepts = [{"id": cid[n], "name": n, "category": c, "category_id": cat_id[c],
                 "synonyms": [] if no_synonyms else syn, "description": d} for n, c, syn, d in K.CONCEPTS]
    relations = [{"from": cid[a], "to": cid[b], "type": t} for a, t, b in K.RELATIONS]
    docs = []
    for i, (title, typ, pub, country, date, tags, summary, body, video) in enumerate(K.ARTICLES, 1):
        docs.append({"id": i, "title": title, "summary": summary, "body": body, "type": typ,
                     "type_id": type_id[typ], "publisher": pub, "country": country, "date": date,
                     "tags": [{"id": cid[t], "name": t, "relevance": r} for t, r in tags],
                     "video": video})
    return KnowledgeIndex(docs, concepts, relations)


def memory_rules():
    """Правила экспертной системы в том же виде, что возвращает db.expert_knowledge()."""
    cid = {c[0]: i + 1 for i, c in enumerate(K.CONCEPTS)}
    rules = []
    for code, conds, then, cf, expl in K.RULES:
        r = {"code": code, "conditions": conds, "cf": cf, "explanation": expl,
             "then_kind": then[0], "then_attribute": None, "then_value": None,
             "id_tag": None, "tag_name": None}
        if then[0] == "fact":
            r["then_attribute"], r["then_value"] = then[1], then[2]
        else:
            r["id_tag"], r["tag_name"] = cid[then[1]], then[1]
        rules.append(r)
    return rules


def memory_questions():
    return [{"attribute": a, "question_text": t, "options_list": o,
             "cond_attribute": c[0] if c else None, "cond_values_list": c[1] if c else []}
            for a, t, o, c in K.QUESTIONS]
