"""Исправление опечаток в запросе (расстояние Дамерау–Левенштейна)."""
from collections import defaultdict


def damerau_levenshtein(a: str, b: str, limit: int = 3) -> int:
    """Число вставок, удалений, замен и перестановок соседних букв.
    Если расстояние заведомо больше limit — возвращает limit + 1."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2 = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        row_min = cur[0]
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if (prev2 is not None and i > 1 and j > 1
                    and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                cur[j] = min(cur[j], prev2[j - 2] + 1)
            row_min = min(row_min, cur[j])
        if row_min > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def _bigrams(word):
    w = f"^{word}$"
    return {w[i:i + 2] for i in range(len(w) - 1)}


class SpellChecker:
    """Словарь словоформ из базы знаний + быстрый подбор кандидатов
    по общим биграммам, затем точная проверка расстоянием."""

    def __init__(self, word_freq: dict):
        self.freq = dict(word_freq)
        self.by_bigram = defaultdict(set)
        for w in self.freq:
            for bg in _bigrams(w):
                self.by_bigram[bg].add(w)

    def known(self, word: str) -> bool:
        return word in self.freq

    def correct(self, word: str):
        """Ближайшее известное слово или None, если исправлять нечего/нечем."""
        if len(word) < 4 or word in self.freq or any(ch.isdigit() for ch in word):
            return None
        limit = 1 if len(word) <= 6 else 2
        grams = _bigrams(word)
        counts = defaultdict(int)
        for bg in grams:
            for cand in self.by_bigram.get(bg, ()):
                counts[cand] += 1
        best, best_key = None, None
        need = max(1, len(grams) - 2 * limit - 2)
        for cand, common in counts.items():
            if common < need:
                continue
            d = damerau_levenshtein(word, cand, limit)
            if d <= limit:
                key = (d, -self.freq[cand])
                if best_key is None or key < best_key:
                    best, best_key = cand, key
        return best
