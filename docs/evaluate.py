"""
Исследование характеристик поиска: качество (P@1, MRR, Recall@5) и скорость
на контрольном наборе запросов, в том числе с отключением отдельных механизмов.

    py docs/evaluate.py   →  docs/evaluation.json
"""
import json
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import search.engine as engine          # noqa: E402
import search.text as text              # noqa: E402
from memory_kb import build_memory_index  # noqa: E402

# Запрос -> заголовки релевантных статей
GOLD = {
    "слово": {
        "газобетон": ["Газобетон: тёплая стена без утеплителя?", "Газобетон или пенобетон: что выбрать"],
        "минвата": ["Минеральная вата: каменная (базальтовая) теплоизоляция", "Минвата или пенополистирол: чем утеплить фасад"],
        "гипсакартон": ["Гипсокартон: виды ГКЛ, ГКЛВ, ГКЛО", "Перегородка из гипсокартона своими руками"],
        "шпаклевка": ["Шпатлёвка: стартовая и финишная"],
        "газоблок": ["Газобетон: тёплая стена без утеплителя?", "Газобетон или пенобетон: что выбрать",
                     "Кладка газобетона на клей"],
        "рубероид": ["Рулонная и обмазочная гидроизоляция фундамента"],
        "самонивелир": ["Стяжка или наливной пол"],
        "ЖБИ": ["Железобетон и армирование фундамента"],
    },
    "словосочетание": {
        "гидроизоляция фундамента": ["Рулонная и обмазочная гидроизоляция фундамента"],
        "чем заменить газобетон": ["Газобетон или пенобетон: что выбрать"],
        "плитка в ванной": ["Плиточный клей и укладка плитки в ванной"],
        "утепление мансарды": ["Утепление кровли и мансарды"],
        "ЦПС для кладки": ["Строительный раствор для кладки кирпича"],
        "маркировка цемента": ["Цемент М500 Д0 и новая маркировка ЦЕМ"],
        "утепление каркасника": ["Каркасный дом: материалы и пирог стены"],
        "основание мягкой кровли": ["Мягкая кровля: устройство и основание"],
    },
    "предложение": {
        "какой утеплитель выбрать для бани чтобы он не горел": [
            "Брус для бани: клееный или профилированный",
            "Минеральная вата: каменная (базальтовая) теплоизоляция",
            "Пожарная безопасность материалов: группы горючести"],
        "какой бетон нужен для ленточного фундамента частного дома из газобетона": [
            "Класс бетона и марка: как выбрать бетон для фундамента"],
        "из чего делают силикатный кирпич": ["Силикатный кирпич: плюсы, минусы и ограничения"],
        "можно ли использовать гипсовую штукатурку в ванной комнате": ["Штукатурка: гипсовая или цементная"],
        "чем отличается керамогранит от обычной керамической плитки для пола": ["Керамогранит или керамическая плитка"],
        "какую тротуарную плитку выбрать для парковки автомобиля во дворе": ["Тротуарная плитка: толщина и основание"],
        "почему зимой разрушается кирпич на цоколе дома": ["Морозостойкость и водопоглощение: почему разрушается кирпич"],
        "как защитить перегородку от шума соседей": ["Звукоизоляция перегородок и стен", "Перегородка из гипсокартона своими руками"],
    },
}

# Additional relevance judgments for the expanded corpus, declared before measurement.
GOLD['слово'].update({
    'грунтовка':['Грунтовка: какую выбрать и когда она действительно нужна'],
    'гидроизаляция':['Рулонная и обмазочная гидроизоляция фундамента','Гидроизоляция ванной: углы, трубы и порядок слоёв'],
})
GOLD['словосочетание'].update({
    'пароизоляция и мембрана':['Пароизоляция и мембрана: почему их нельзя менять местами'],
    'уход за бетоном':['Бетон после заливки: уход важнее добавления воды'],
})
GOLD['предложение'].update({
    'как рассчитать количество плитки для ванной':['Как посчитать плитку: площадь, подрезка и запас'],
    'почему грунтовка не укрепляет рыхлую стену':['Грунтовка: какую выбрать и когда она действительно нужна'],
})

CONFIGS = [
    ("full", "Полная система"),
    ("no_spell", "Без исправления опечаток"),
    ("no_onto", "Без синонимов и онтологии"),
    ("no_stem", "Без стемминга"),
]


@contextmanager
def evaluation_mode(config):
    """Keep preprocessing consistent for BOTH indexing and query evaluation."""
    real_stem = text._stem
    if config == "no_stem":
        identity = lambda w: w.lower().replace("ё", "е")          # noqa: E731
        text._stem = identity
        text.stem.cache_clear()
    try:
        yield
    finally:
        text._stem = real_stem
        text.stem.cache_clear()


def build(config):
    ix = build_memory_index(no_synonyms=(config == "no_onto"))
    if config == "no_onto":
        ix._expand = lambda *a, **k: None
    if config == "no_spell":
        ix.speller.correct = lambda w: None
    return ix


def evaluate(config):
    with evaluation_mode(config):
        return _evaluate(config)


def _evaluate(config):
    ix = build(config)
    out = {}
    for kind, queries in GOLD.items():
        p1, rr, rec5, times, per_query = [], [], [], [], []
        for q, rel in queries.items():
            res = ix.search(q, limit=10)
            titles = [r["doc"]["title"] for r in res["results"]]
            rank = next((i + 1 for i, t in enumerate(titles) if t in rel), None)
            p1.append(1.0 if rank == 1 else 0.0)
            rr.append(1.0 / rank if rank else 0.0)
            rec5.append(len(set(titles[:5]) & set(rel)) / len(rel))
            ts = []
            for _ in range(30):
                t0 = time.perf_counter()
                ix.search(q)
                ts.append((time.perf_counter() - t0) * 1000)
            times.append(statistics.median(ts))
            per_query.append({"q": q, "rank": rank, "top": titles[0] if titles else None,
                              "ms": round(statistics.median(ts), 2), "total": res["total"],
                              "answer": bool(res["answer"]), "words": len(res["query"].words)})
        out[kind] = {"P@1": statistics.mean(p1), "MRR": statistics.mean(rr), "R@5": statistics.mean(rec5),
                     "ms": statistics.mean(times), "ms_max": max(times), "queries": per_query}
    return out, ix.stats()


if __name__ == "__main__":
    result = {}
    for key, label in CONFIGS:
        res, stats = evaluate(key)
        result[key] = {"label": label, "by_kind": res, "stats": stats}
        print(label, {k: (round(v["P@1"], 2), round(v["MRR"], 2), round(v["R@5"], 2), round(v["ms"], 2))
                      for k, v in res.items()})
    (ROOT / "docs" / "evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
