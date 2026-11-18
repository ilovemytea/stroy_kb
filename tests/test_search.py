"""Тесты поискового движка на данных data/knowledge.py (SQL Server не нужен)."""
import pytest

from memory_kb import build_memory_index
from search.engine import MAX_QUERY_WORDS
from search.spell import damerau_levenshtein
from search.stemmer import stem


@pytest.fixture(scope="module")
def ix():
    return build_memory_index()


def top_titles(ix, q, n=3):
    return [r["doc"]["title"] for r in ix.search(q)["results"][:n]]


# ---------- стемминг ----------
@pytest.mark.parametrize("forms, base", [
    (["кирпич", "кирпича", "кирпичами", "кирпичу"], "кирпич"),
    (["утеплитель", "утеплителя", "утеплителей", "утеплителем"], "утеплител"),
    (["морозостойкость", "морозостойкий", "морозостойкого"], "морозостойк"),
    (["гипсокартон", "гипсокартона", "гипсокартонные"], "гипсокартон"),
])
def test_stemmer_groups_word_forms(forms, base):
    assert {stem(f) for f in forms} == {base}


def test_damerau_levenshtein():
    assert damerau_levenshtein("бетон", "бетон") == 0
    assert damerau_levenshtein("бетон", "бтеон") == 1          # перестановка
    assert damerau_levenshtein("гипсакартон", "гипсокартон") == 1


# ---------- три вида запросов ----------
def test_query_kind_by_length(ix):
    assert ix.parse("газобетон").kind == "слово"
    assert ix.parse("кирпич для фундамента").kind == "словосочетание"
    assert ix.parse("какой утеплитель выбрать для бани чтобы он не горел").kind == "предложение"


def test_word_query(ix):
    assert "Газобетон" in top_titles(ix, "газобетон")[0] or "Газобетон" in top_titles(ix, "газобетон")[1]


def test_word_forms_are_found(ix):
    assert top_titles(ix, "кирпичами")[:2] == top_titles(ix, "кирпич")[:2]


def test_phrase_query(ix):
    titles = top_titles(ix, "гидроизоляция фундамента")
    assert titles[0] == "Рулонная и обмазочная гидроизоляция фундамента"


def test_sentence_query(ix):
    res = ix.search("какой бетон нужен для ленточного фундамента частного дома из газобетона")
    assert res["results"][0]["doc"]["title"].startswith("Класс бетона и марка")
    assert "B20" in res["answer"]["text_html"]


def test_query_limited_to_15_words(ix):
    q = " ".join(["бетон"] * 20)
    p = ix.parse(q)
    assert p.truncated and len(p.words) == MAX_QUERY_WORDS


# ---------- «умные» возможности ----------
def test_synonym_expansion(ix):
    """«минвата» — синоним понятия «Минеральная вата»."""
    res = ix.search("минвата")
    assert res["results"][0]["doc"]["title"].startswith("Минеральная вата")


def test_abbreviation(ix):
    res = ix.search("ГКЛВ")
    assert res["results"][0]["doc"]["title"].startswith("Гипсокартон: виды")


def test_typo_correction(ix):
    res = ix.search("гипсакартон")
    assert res["query"].corrected == "гипсокартон"
    assert res["total"] > 0


def test_intent_replace_uses_ontology(ix):
    res = ix.search("чем заменить газобетон")
    card = res["concept_cards"][0]
    assert card["focus"] == "может заменить"
    assert "Пенобетон" in [c["name"] for c in card["relations"]["может заменить"]]


def test_intent_made_of(ix):
    res = ix.search("из чего делают силикатный кирпич")
    names = [c["name"] for c in res["concept_cards"][0]["relations"]["изготавливается из"]]
    assert set(names) == {"Известь", "Песок"}
    assert "извести" in res["answer"]["text_html"]


def test_hierarchy_expansion(ix):
    """Запрос по родовому понятию находит статьи о его видах."""
    titles = top_titles(ix, "утеплитель", 6)
    assert any("Минвата" in t or "Минеральная вата" in t for t in titles)


def test_highlight_escapes_html(ix):
    assert ix.highlight("<b>бетон</b>", {stem("бетон")}) == "&lt;b&gt;<mark>бетон</mark>&lt;/b&gt;"


def test_nonsense_returns_nothing(ix):
    assert ix.search("абырвалг квазистроение")["total"] == 0


def test_suggest(ix):
    assert "Газобетон" in ix.suggest("газоб")


def test_search_is_fast(ix):
    import time
    t0 = time.perf_counter()
    for _ in range(50):
        ix.search("какой утеплитель выбрать для бани чтобы он не горел")
    assert (time.perf_counter() - t0) / 50 < 0.05     # < 50 мс на запрос
