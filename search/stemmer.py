"""
Стеммер русского языка (алгоритм Snowball / Портера для русского).

Отрезает от слова окончание и суффиксы, чтобы разные словоформы
сводились к одной основе:
    кирпич, кирпича, кирпичами, кирпичный  ->  кирпич
    утеплитель, утеплителя, утеплителей    ->  утеплител
"""

VOWELS = set("аеиоуыэюя")

# Окончания упорядочены от длинных к коротким — ищется самое длинное совпадение.
def _sorted(*groups):
    return tuple(sorted(set(s for g in groups for s in g.split()), key=len, reverse=True))

PERFECTIVE_GERUND_1 = _sorted("в вши вшись")              # после а / я
PERFECTIVE_GERUND_2 = _sorted("ив ивши ившись ыв ывши ывшись")
REFLEXIVE = _sorted("ся сь")
ADJECTIVE = _sorted("ее ие ые ое ими ыми ей ий ый ой ем им ым ом его ого ему ому "
                    "их ых ую юю ая яя ою ею")
PARTICIPLE_1 = _sorted("ем нн вш ющ щ")                   # после а / я
PARTICIPLE_2 = _sorted("ивш ывш ующ")
VERB_1 = _sorted("ла на ете йте ли й л ем н ло но ет ют ны ть ешь нно")  # после а / я
VERB_2 = _sorted("ила ыла ена ейте уйте ите или ыли ей уй ил ыл им ым ен ило ыло ено "
                 "ят ует уют ит ыт ены ить ыть ишь ую ю")
NOUN = _sorted("а ев ов ие ье е иями ями ами еи ии и ией ей ой ий й иям ям ием ем ам ом "
               "о у ах иях ях ы ь ию ью ю ия ья я")
SUPERLATIVE = _sorted("ейш ейше")
DERIVATIONAL = _sorted("ост ость")


def _regions(word):
    """Возвращает начала областей RV и R2 (индексы в слове)."""
    rv = len(word)
    for i, ch in enumerate(word):
        if ch in VOWELS:
            rv = i + 1
            break

    def next_region(start):
        for i in range(start + 1, len(word)):
            if word[i] not in VOWELS and word[i - 1] in VOWELS:
                return i + 1
        return len(word)

    r1 = next_region(0)
    r2 = next_region(r1)
    return rv, r2


def _strip(word, start, suffixes, after_a_ya=False):
    """Отрезает первое подходящее окончание, лежащее в области [start:].
    Если after_a_ya — окончание должно идти после «а» или «я»."""
    for s in suffixes:
        if word.endswith(s) and len(word) - len(s) >= start:
            if after_a_ya:
                pos = len(word) - len(s) - 1
                if pos < start or word[pos] not in "ая":
                    continue
            return word[: len(word) - len(s)], True
    return word, False


def _strip_pair(word, start, group1, group2):
    """Пробует обе группы окончаний, выбирая самое длинное совпадение."""
    best = None
    for s in group1:
        if word.endswith(s) and len(word) - len(s) >= start:
            pos = len(word) - len(s) - 1
            if pos >= start and word[pos] in "ая":
                best = s
                break
    for s in group2:
        if word.endswith(s) and len(word) - len(s) >= start:
            if best is None or len(s) > len(best):
                best = s
            break
    if best is None:
        return word, False
    return word[: len(word) - len(best)], True


def stem(word: str) -> str:
    word = word.lower().replace("ё", "е")
    if len(word) <= 2 or not any(ch in VOWELS for ch in word):
        return word

    rv, r2 = _regions(word)

    # Шаг 1
    w, ok = _strip_pair(word, rv, PERFECTIVE_GERUND_1, PERFECTIVE_GERUND_2)
    if not ok:
        w, _ = _strip(w, rv, REFLEXIVE)
        # ADJECTIVAL = (PARTICIPLE) + ADJECTIVE
        w2, ok = _strip(w, rv, ADJECTIVE)
        if ok:
            w3, _ = _strip_pair(w2, rv, PARTICIPLE_1, PARTICIPLE_2)
            w = w3
        else:
            w2, ok = _strip_pair(w, rv, VERB_1, VERB_2)
            if ok:
                w = w2
            else:
                w, _ = _strip(w, rv, NOUN)

    # Шаг 2: окончание «и»
    if w.endswith("и") and len(w) - 1 >= rv:
        w = w[:-1]

    # Шаг 3: словообразовательный суффикс в R2
    w, _ = _strip(w, r2, DERIVATIONAL)

    # Шаг 4
    if w.endswith("нн") and len(w) - 2 >= rv:
        w = w[:-1]
    else:
        w2, ok = _strip(w, rv, SUPERLATIVE)
        if ok:
            w = w2
            if w.endswith("нн"):
                w = w[:-1]
        elif w.endswith("ь") and len(w) - 1 >= rv:
            w = w[:-1]
    return w
