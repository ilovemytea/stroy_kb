"""
Поисковая машина базы знаний «СтройМир».

Запрос (слово, словосочетание или предложение до 15 слов) проходит этапы:
  1. нормализация и токенизация, ограничение длины запроса;
  2. исправление опечаток по словарю базы знаний;
  3. стемминг и удаление стоп-слов / вопросительных слов;
  4. распознавание понятий онтологии (в т.ч. многословных: «минеральная вата»)
     и расширение запроса синонимами и подчинёнными понятиями;
  5. определение намерения пользователя («чем заменить», «для чего», «что такое»);
  6. ранжирование BM25F по полям документа с учётом покрытия запроса,
     близости слов, тегов документа;
  7. построение сниппетов, «быстрого ответа» и карточки понятия.
"""
import html
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field

from .spell import SpellChecker
from .text import (QUESTION_WORDS, STOPWORDS, content_stems, normalize, sentences, stem,
                   tokenize, tokenize_spans)

MAX_QUERY_WORDS = 15

# Веса полей документа для BM25F
FIELD_WEIGHTS = {"title": 3.0, "tags": 2.0, "summary": 1.5, "body": 1.0}
K1, B = 1.2, 0.75

# Веса расширений запроса
W_SYNONYM = 0.7
W_CHILD = 0.35
W_INTENT = 0.3

RELATION_LABELS = {
    "является": ("является видом", "виды"),
    "применяется_для": ("применяется для", "применяют"),
    "изготавливается_из": ("изготавливается из", "сырьё для"),
    "обладает_свойством": ("обладает свойством", "свойство материалов"),
    "заменяет": ("может заменить", "можно заменить на"),
    "регламентируется": ("регламентируется", "регламентирует"),
    "несовместим_с": ("несовместим с", "несовместим с"),
    "часть": ("входит в", "состоит из"),
}

# Намерения: регулярное выражение по нормализованному запросу -> тип связи онтологии
INTENTS = [
    ("define", re.compile(r"^что так|^что это|что такое|определени|это что"),
     None, "Определение"),
    ("replace", re.compile(r"замен|аналог|вместо|альтернатив"), "заменяет",
     "Чем можно заменить"),
    ("usage", re.compile(r"для чего|где (?:применя|использ)|применени|применя|использ|подходит для"),
     "применяется_для", "Где применяется"),
    ("made_of", re.compile(r"из чего|состав|сырь|изготав|делают|производ"),
     "изготавливается_из", "Из чего изготавливается"),
    ("property", re.compile(r"свойств|характеристик|плотност|теплопровод|прочност|морозостойк"),
     "обладает_свойством", "Свойства"),
    ("standard", re.compile(r"гост|стб|норматив|стандарт|сто\b|снип|тр тс"),
     "регламентируется", "Нормативные документы"),
    ("kinds", re.compile(r"виды|вид |типы|разновидност|какие бывают|классификац"),
     "является", "Виды"),
]
INTENT_TRIGGER_WORDS = set("""
заменить замена заменять заменит аналог аналоги аналогов вместо альтернатива
применяется применение применять использовать используется используют использование
состав сырье изготавливают изготавливается делают производят производство
свойства свойство характеристики характеристика
гост стб норматив нормативы стандарт стандарты
виды вид типы разновидности классификация бывают такое определение
""".split())
INTENT_TRIGGER_STEMS = {stem(w) for w in INTENT_TRIGGER_WORDS}


@dataclass
class QueryTerm:
    stem: str
    weight: float
    origin: str               # query | synonym | child | intent
    groups: frozenset         # какие слова исходного запроса «закрывает» термин
    label: str = ""


@dataclass
class ParsedQuery:
    raw: str
    words: list
    truncated: bool
    kind: str                 # слово | словосочетание | предложение
    corrected: str = None
    terms: list = field(default_factory=list)
    n_groups: int = 0
    concepts: list = field(default_factory=list)   # id найденных понятий
    intent: tuple = None
    orig_stems: list = field(default_factory=list)


class KnowledgeIndex:
    def __init__(self, documents, concepts, relations, products=(), popular_queries=()):
        """
        documents: [{id, title, summary, body, type, type_id, publisher, country, date,
                     tags: [{id, name, relevance}], video}]
        concepts:  [{id, name, category, category_id, synonyms: [..], description}]
        relations: [{from, to, type}]
        products:  [{id, name, category, manufacturer, price, unit, ...}]
        """
        self.docs = {d["id"]: d for d in documents}
        self.concepts = {c["id"]: c for c in concepts}
        self.relations = list(relations)
        self.products = list(products)
        self.popular_queries = list(popular_queries)
        self._build()

    # ------------------------------------------------------------------ индекс
    def _build(self):
        t0 = time.perf_counter()
        self.postings = defaultdict(dict)        # stem -> doc_id -> {field: tf}
        self.positions = {}                       # doc_id -> stem -> [pos]
        self.field_len = defaultdict(dict)        # doc_id -> field -> len
        word_freq = defaultdict(int)

        for doc_id, d in self.docs.items():
            tag_text = " ".join(
                " ".join([self.concepts[t["id"]]["name"]] + self.concepts[t["id"]]["synonyms"])
                for t in d.get("tags", []) if t["id"] in self.concepts)
            fields = {"title": d["title"], "summary": d.get("summary") or "",
                      "body": d.get("body") or "", "tags": tag_text}
            pos_map = defaultdict(list)
            pos = 0
            for fname, text in fields.items():
                words = [w for w in tokenize(text) if w not in STOPWORDS]
                for w in words:
                    word_freq[w] += 1
                stems = [stem(w) for w in words]
                self.field_len[doc_id][fname] = len(stems)
                for s in stems:
                    entry = self.postings[s].setdefault(doc_id, {})
                    entry[fname] = entry.get(fname, 0) + 1
                if fname != "tags":
                    for s in stems:
                        pos_map[s].append(pos)
                        pos += 1
                    pos += 5   # разрыв между полями, чтобы фраза не «склеивалась»
            self.positions[doc_id] = dict(pos_map)

        n = max(1, len(self.docs))
        self.avg_len = {f: sum(self.field_len[d].get(f, 0) for d in self.docs) / n or 1
                        for f in FIELD_WEIGHTS}
        self.idf = {s: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5))
                    for s, p in self.postings.items()}

        # Словарь понятий: последовательность основ -> id понятия
        self.concept_phrases = {}
        for c in self.concepts.values():
            for name in [c["name"]] + c["synonyms"]:
                key = tuple(content_stems(name))
                if key:
                    self.concept_phrases.setdefault(key, c["id"])
                for w in tokenize(name):
                    word_freq[w] += 1
        self.max_phrase = max((len(k) for k in self.concept_phrases), default=1)

        for p in self.products:
            for w in tokenize(p["name"] + " " + p.get("category", "")):
                word_freq[w] += 1

        self.out_rel = defaultdict(list)
        self.in_rel = defaultdict(list)
        for r in self.relations:
            self.out_rel[r["from"]].append(r)
            self.in_rel[r["to"]].append(r)

        self.speller = SpellChecker(word_freq)
        self.vocabulary_size = len(word_freq)
        self.index_terms = len(self.postings)
        self.build_ms = (time.perf_counter() - t0) * 1000

    # ---------------------------------------------------------- разбор запроса
    def parse(self, raw: str) -> ParsedQuery:
        words = tokenize(raw)
        truncated = len(words) > MAX_QUERY_WORDS
        words = words[:MAX_QUERY_WORDS]
        kind = ("слово" if len(words) <= 1 else
                "словосочетание" if len(words) <= 4 else "предложение")
        q = ParsedQuery(raw=raw, words=words, truncated=truncated, kind=kind)

        # Исправление опечаток
        fixed, changed = [], False
        for w in words:
            c = None if (w in STOPWORDS or w in QUESTION_WORDS) else self.speller.correct(w)
            if c and stem(c) != stem(w):
                fixed.append(c)
                changed = True
            else:
                fixed.append(w)
        if changed:
            q.corrected = " ".join(fixed)
        words = fixed

        normalized = " ".join(words)
        for name, rx, rel_type, title in INTENTS:
            if rx.search(normalized):
                q.intent = (name, rel_type, title)
                break

        # Значимые слова: без стоп-слов и вопросительных слов
        content = [w for w in words if w not in STOPWORDS and w not in QUESTION_WORDS]
        if not content:
            content = [w for w in words if w not in STOPWORDS] or words
        stems = [stem(w) for w in content]

        groups = []        # индексы «смысловых» слов
        for i, s in enumerate(stems):
            if s in INTENT_TRIGGER_STEMS and q.intent and len(stems) > 1:
                q.terms.append(QueryTerm(s, W_INTENT, "intent", frozenset(), content[i]))
            else:
                groups.append(i)
                q.terms.append(QueryTerm(s, 1.0, "query", frozenset([i]), content[i]))
        q.n_groups = len(groups)
        q.orig_stems = [stems[i] for i in groups]

        # Поиск понятий онтологии в запросе (самое длинное совпадение)
        i = 0
        while i < len(stems):
            for L in range(min(self.max_phrase, len(stems) - i), 0, -1):
                cid = self.concept_phrases.get(tuple(stems[i:i + L]))
                if cid is not None:
                    span = frozenset(range(i, i + L)) & frozenset(groups)
                    if cid not in q.concepts:
                        q.concepts.append(cid)
                        self._expand(q, cid, span or frozenset(range(i, i + L)))
                    i += L
                    break
            else:
                i += 1
        return q

    def _expand(self, q, cid, span):
        """Расширение запроса синонимами понятия и названиями его видов."""
        c = self.concepts[cid]
        have = {t.stem for t in q.terms}
        for name in [c["name"]] + c["synonyms"]:
            for s in content_stems(name):
                if s not in have:
                    q.terms.append(QueryTerm(s, W_SYNONYM, "synonym", span, name))
                    have.add(s)
        for r in self.in_rel.get(cid, []):
            if r["type"] == "является" and r["from"] in self.concepts:
                child = self.concepts[r["from"]]
                for s in content_stems(child["name"]):
                    if s not in have:
                        q.terms.append(QueryTerm(s, W_CHILD, "child", span, child["name"]))
                        have.add(s)

    # ------------------------------------------------------------ ранжирование
    def _bm25(self, term, doc_id):
        p = self.postings.get(term.stem, {}).get(doc_id)
        if not p:
            return 0.0
        tf = 0.0
        for f, cnt in p.items():
            norm = 1 - B + B * self.field_len[doc_id].get(f, 0) / self.avg_len[f]
            tf += FIELD_WEIGHTS[f] * cnt / norm
        return self.idf.get(term.stem, 0) * tf / (K1 + tf)

    def _proximity(self, doc_id, stems):
        """Минимальное окно, содержащее максимум разных слов запроса."""
        pos = self.positions.get(doc_id, {})
        events = sorted((p, s) for s in set(stems) for p in pos.get(s, []))
        present = {s for _, s in events}
        if len(present) < 2:
            return 0.0, len(present)
        need, best = len(present), None
        count, left = defaultdict(int), 0
        have = 0
        for right, (p, s) in enumerate(events):
            count[s] += 1
            if count[s] == 1:
                have += 1
            while have == need:
                span = p - events[left][0] + 1
                best = span if best is None else min(best, span)
                ls = events[left][1]
                count[ls] -= 1
                if count[ls] == 0:
                    have -= 1
                left += 1
        return need / best, need

    def search(self, raw, type_id=None, category_id=None, limit=20):
        t0 = time.perf_counter()
        q = self.parse(raw)
        candidates = set()
        for t in q.terms:
            candidates.update(self.postings.get(t.stem, {}).keys())

        # Понятия запроса дают бонус статьям со своим тегом, их виды (по связи «является») — половинный
        concept_w = {}
        for cid in q.concepts:
            for r in self.in_rel.get(cid, []):
                if r["type"] == "является":
                    concept_w.setdefault(r["from"], 0.5)
            concept_w[cid] = 1.0

        scored = []
        for doc_id in candidates:
            d = self.docs[doc_id]
            if type_id and d.get("type_id") != type_id:
                continue
            if category_id and not any(self.concepts.get(t["id"], {}).get("category_id") == category_id
                                       for t in d.get("tags", [])):
                continue
            bm25, covered, matched = 0.0, set(), []
            for t in q.terms:
                s = self._bm25(t, doc_id)
                if s > 0:
                    bm25 += t.weight * s
                    covered |= t.groups
                    matched.append(t)
            if bm25 <= 0:
                continue
            coverage = len(covered) / q.n_groups if q.n_groups else 1.0
            score = bm25 * (0.3 + 0.7 * coverage ** 2)
            prox, _ = self._proximity(doc_id, q.orig_stems) if q.n_groups > 1 else (0.0, 0)
            score *= 1 + 0.6 * prox
            tag_bonus = max((float(t["relevance"]) * concept_w[t["id"]] for t in d.get("tags", [])
                             if t["id"] in concept_w), default=0)
            score *= 1 + 0.5 * float(tag_bonus)
            scored.append((score, doc_id, {
                "bm25": round(bm25, 3), "coverage": round(coverage, 2),
                "proximity": round(prox, 2), "tag": round(float(tag_bonus), 2),
                "matched": sorted({t.label for t in matched}),
            }))

        scored.sort(key=lambda x: -x[0])
        if scored:
            top = scored[0][0]
            scored = [s for s in scored if s[0] >= top * 0.08]

        hl = {t.stem for t in q.terms if t.origin != "intent"}
        results = []
        for score, doc_id, explain in scored[:limit]:
            d = self.docs[doc_id]
            results.append({
                "doc": d, "score": round(score, 3), "explain": explain,
                "title_html": self.highlight(d["title"], hl),
                "snippet_html": self.snippet(d, hl),
            })

        answer = self._answer(q, scored, hl)
        took = (time.perf_counter() - t0) * 1000
        return {
            "query": q, "results": results, "total": len(scored), "answer": answer,
            "concept_cards": [self.concept_card(cid, q.intent) for cid in q.concepts[:2]],
            "related": self._related(q),
            "products": self._products(q),
            "took_ms": round(took, 2),
        }

    # ---------------------------------------------------------- представление
    def highlight(self, text, stems):
        out, last = [], 0
        for w, a, b in tokenize_spans(text):
            if stem(w) in stems and w not in STOPWORDS:
                out.append(html.escape(text[last:a]))
                out.append(f"<mark>{html.escape(text[a:b])}</mark>")
                last = b
        out.append(html.escape(text[last:]))
        return "".join(out)

    def _sentence_score(self, sent, stems):
        found = {stem(w) for w in tokenize(sent)} & stems
        return len(found)

    def snippet(self, d, stems, max_len=260):
        sents = sentences((d.get("summary") or "") + "\n" + (d.get("body") or ""))
        if not sents:
            return ""
        best = max(range(len(sents)), key=lambda i: (self._sentence_score(sents[i], stems), -i))
        text = sents[best]
        if len(text) < max_len // 2 and best + 1 < len(sents):
            text += " " + sents[best + 1]
        if len(text) > max_len:
            text = text[:max_len].rsplit(" ", 1)[0] + "…"
        return self.highlight(text, stems)

    def _answer(self, q, scored, hl):
        """«Быстрый ответ»: лучшее предложение из первых документов выдачи."""
        if not scored or q.n_groups == 0:
            return None
        orig = set(q.orig_stems)
        want = orig | {t.stem for t in q.terms if t.origin == "synonym"}
        best = None
        for score, doc_id, _ in scored[:3]:
            d = self.docs[doc_id]
            for s in sentences(d.get("body") or ""):
                stems_s = {stem(w) for w in tokenize(s)}
                cov = len(stems_s & orig) / len(orig)
                syn = len(stems_s & want)
                intent_hit = 0
                if q.intent:
                    intent_hit = int(bool(stems_s & INTENT_TRIGGER_STEMS))
                key = (cov + 0.15 * syn + 0.3 * intent_hit) * (1 + score / (scored[0][0] * 4))
                if 40 <= len(s) <= 400 and (best is None or key > best[0]):
                    best = (key, s, d)
        if best and best[0] >= 0.6 and (q.kind != "слово" or q.intent):
            return {"text_html": self.highlight(best[1], hl), "doc": best[2]}
        return None

    def concept_card(self, cid, intent=None):
        c = self.concepts[cid]
        groups = defaultdict(list)
        for r in self.out_rel.get(cid, []):
            if r["to"] in self.concepts:
                groups[RELATION_LABELS.get(r["type"], (r["type"],))[0]].append(self.concepts[r["to"]])
        for r in self.in_rel.get(cid, []):
            if r["from"] in self.concepts:
                label = RELATION_LABELS.get(r["type"], (r["type"], r["type"]))[1]
                groups[label].append(self.concepts[r["from"]])
        focus = None
        if intent and intent[1]:
            labels = RELATION_LABELS.get(intent[1], ())
            for lbl in labels:
                if groups.get(lbl):
                    focus = lbl
                    break
        return {"concept": c, "relations": dict(groups), "focus": focus,
                "intent_title": intent[2] if intent else None}

    def _related(self, q):
        out, seen = [], set(q.concepts)
        for cid in q.concepts:
            for r in self.out_rel.get(cid, []) + self.in_rel.get(cid, []):
                other = r["to"] if r["from"] == cid else r["from"]
                if other not in seen and other in self.concepts:
                    seen.add(other)
                    out.append(self.concepts[other])
        return out[:8]

    def _products(self, q):
        want = {t.stem: t.weight for t in q.terms if t.origin in ("query", "synonym")}
        if not want:
            return []
        res = []
        for p in self.products:
            stems_p = set(content_stems(f'{p["name"]} {p.get("category", "")}'))
            s = sum(w for st, w in want.items() if st in stems_p)
            if s > 0:
                res.append((s, p))
        res.sort(key=lambda x: -x[0])
        return [p for _, p in res[:5]]

    # ---------------------------------------------------------- подсказки
    def suggest(self, prefix, limit=8):
        words = tokenize(prefix)
        if not words:
            return []
        head, last = [stem(w) for w in words[:-1]], words[-1]
        cands = []
        for qtext, cnt in self.popular_queries:
            cands.append((0, -cnt, qtext))
        for c in self.concepts.values():
            for n in [c["name"]] + c["synonyms"]:
                cands.append((1, 0, n))
        for d in self.docs.values():
            cands.append((2, 0, d["title"]))
        out, seen = [], set()
        for prio, pop, text in sorted(cands):
            toks = tokenize(text)
            tstems = {stem(t) for t in toks}
            if all(h in tstems for h in head) and any(t.startswith(last) for t in toks):
                key = normalize(text)
                if key not in seen:
                    seen.add(key)
                    out.append(text)
                    if len(out) >= limit:
                        break
        return out

    def stats(self):
        return {"documents": len(self.docs), "concepts": len(self.concepts),
                "relations": len(self.relations), "index_terms": self.index_terms,
                "vocabulary": self.vocabulary_size, "build_ms": round(self.build_ms, 1)}
