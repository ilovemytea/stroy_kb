"""
Продукционная экспертная система подбора строительных материалов.

Знания — правила вида
    ЕСЛИ атрибут1 = значение1 И атрибут2 = значение2 ... ТО заключение (CF)
Заключение — либо новый факт рабочей памяти (атрибут = значение),
либо рекомендация материала (понятие онтологии) с коэффициентом уверенности.

Вывод — прямая цепочка рассуждений (forward chaining): правила применяются,
пока в рабочую память добавляются новые факты. Коэффициенты уверенности
нескольких правил об одном материале объединяются по схеме MYCIN:
    оба > 0:          CF = CF1 + CF2·(1 − CF1)
    оба < 0:          CF = CF1 + CF2·(1 + CF1)
    разных знаков:    CF = (CF1 + CF2) / (1 − min(|CF1|, |CF2|))
"""


def combine_cf(a, b):
    if a >= 0 and b >= 0:
        return a + b * (1 - a)
    if a < 0 and b < 0:
        return a + b * (1 + a)
    return (a + b) / (1 - min(abs(a), abs(b)))


def visible_questions(questions, answers):
    """Вопросы, которые нужно задать при текущих ответах (условные вопросы)."""
    out = []
    for q in questions:
        if q.get("cond_attribute"):
            if answers.get(q["cond_attribute"]) not in q["cond_values_list"]:
                continue
        out.append(q)
    return out


def infer(rules, answers, threshold=0.2):
    """
    rules: [{code, conditions: [(attr, value)], then_kind, then_attribute, then_value,
             id_tag, tag_name, cf, explanation}]
    answers: {атрибут: значение}
    Возвращает рекомендации, отклонённые материалы, выведенные факты и трассу вывода.
    """
    facts = {k: v for k, v in answers.items() if v}
    fired = set()
    trace = []
    derived = {}
    cf_by_tag = {}
    rules_by_tag = {}

    step = 0
    changed = True
    while changed:                      # цикл «распознавание — действие»
        changed = False
        for r in rules:
            if r["code"] in fired:
                continue
            if not all(facts.get(a) == v for a, v in r["conditions"]):
                continue
            fired.add(r["code"])
            step += 1
            entry = {"step": step, "rule": r, "result": None}
            if r["then_kind"] == "fact":
                attr, val = r["then_attribute"], r["then_value"]
                if facts.get(attr) != val:
                    facts[attr] = val
                    derived[attr] = val
                    changed = True      # новый факт может активировать другие правила
                entry["result"] = f"{attr} = {val}"
            else:
                tid = r["id_tag"]
                prev = cf_by_tag.get(tid)
                cf_by_tag[tid] = r["cf"] if prev is None else combine_cf(prev, r["cf"])
                rules_by_tag.setdefault(tid, {"name": r["tag_name"], "rules": []})["rules"].append(r)
                entry["result"] = f"{r['tag_name']}: CF {prev if prev is not None else 0:+.2f} → {cf_by_tag[tid]:+.2f}"
            trace.append(entry)

    items = [{"id_tag": tid, "name": rules_by_tag[tid]["name"], "cf": round(cf, 3),
              "rules": rules_by_tag[tid]["rules"]} for tid, cf in cf_by_tag.items()]
    recommended = sorted((i for i in items if i["cf"] >= threshold), key=lambda i: -i["cf"])
    rejected = sorted((i for i in items if i["cf"] < 0), key=lambda i: i["cf"])
    return {"recommended": recommended, "rejected": rejected, "facts": facts,
            "derived": derived, "trace": trace}
