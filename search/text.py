"""Нормализация текста: токенизация, стоп-слова, разбиение на предложения."""
import re
from functools import lru_cache

from .stemmer import stem as _stem

# Слово — буквы/цифры, допускаются внутренние дефис и точка/запятая в числах
# («12.5», «М-150», «200x100»).
TOKEN_RE = re.compile(r"[0-9a-zа-яё]+(?:[-.,x×][0-9a-zа-яё]+)*", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z0-9«])")

STOPWORDS = set("""
а без более бы был была были было быть в вам вас весь во вот все всего всех вы
где да даже для до его ее ей ему если есть еще же за здесь и из или им их к как
ко когда кто ли либо мне может мы на над надо наш не него нее нет ни них но ну о
об однако он она они оно от очень по под при про с со так также такой там те тем
то того тоже той только том тот ту ты у уже хотя чего чей чем что чтобы чье чья
эта эти это этот я который которая которые которых которой котором можно нужно
мой моя мое мои свой своя свое свои сам сама само сами себя себе ваш ваша ваше
будет будут есть является являются
""".split())

# Вопросительные слова — значимы для определения намерения, но не для поиска.
QUESTION_WORDS = set("""
что какой какая какое какие каких каком какую как почему зачем сколько где куда
откуда чем чему кем когда ли разве можно ли лучше лучший лучшая выбрать подобрать
посоветуйте подскажите расскажите скажите
""".split())


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def tokenize(text: str):
    """Список словоформ (в нижнем регистре)."""
    return [m.group(0) for m in TOKEN_RE.finditer(normalize(text))]


def tokenize_spans(text: str):
    """Словоформы с позициями в исходной строке — для подсветки."""
    low = normalize(text)
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(low)]


@lru_cache(maxsize=200_000)
def stem(word: str) -> str:
    # Числа, марки и размеры («м500», «12.5», «200x100») не стеммим.
    if any(ch.isdigit() for ch in word):
        return word
    return _stem(word)


def is_stop(word: str) -> bool:
    return word in STOPWORDS


def content_stems(text: str):
    """Основы значимых слов (без стоп-слов)."""
    return [stem(w) for w in tokenize(text) if w not in STOPWORDS]


def sentences(text: str):
    parts = []
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if para:
            parts.extend(s.strip() for s in SENTENCE_RE.split(para) if s.strip())
    return parts
