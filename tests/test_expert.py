"""Тесты машины вывода экспертной системы."""
import pytest

from expert import combine_cf, infer, visible_questions
from memory_kb import memory_questions, memory_rules


@pytest.fixture(scope="module")
def rules():
    return memory_rules()


def names(items):
    return [i["name"] for i in items]


def test_combine_cf():
    assert combine_cf(0.6, 0.5) == pytest.approx(0.8)
    assert combine_cf(-0.6, -0.5) == pytest.approx(-0.8)
    assert combine_cf(0.8, -0.3) == pytest.approx(0.5 / 0.7)


def test_forward_chaining_derives_facts(rules):
    r = infer(rules, {"element": "Фундамент"})
    # Фундамент -> zone=грунт -> need_water=да -> need_moisture=да
    assert r["derived"] == {"zone": "грунт", "need_water": "да", "need_moisture": "да"}
    assert names(r["recommended"])[0] in ("Бетон", "Железобетон")
    assert "Гипсокартон" in names(r["rejected"])


def test_wet_partition(rules):
    r = infer(rules, {"element": "Перегородка", "humidity": "Влажное помещение"})
    assert names(r["recommended"])[0] == "Влагостойкий гипсокартон"
    assert "Гипсокартон" in names(r["rejected"])


def test_bath_insulation_is_not_polystyrene(rules):
    r = infer(rules, {"element": "Утепление", "building": "Баня", "place": "Фасад"})
    assert names(r["recommended"])[0] == "Минеральная вата"
    assert "Пенополистирол" in names(r["rejected"])


def test_flat_roof(rules):
    r = infer(rules, {"element": "Кровля", "slope": "Плоская", "budget": "Средний"})
    assert names(r["recommended"])[0] == "Рулонная гидроизоляция"
    assert "Металлочерепица" in names(r["rejected"])


def test_cheap_wall(rules):
    r = infer(rules, {"element": "Наружная стена", "building": "Каменный дом", "load": "Несущая",
                      "budget": "Эконом", "speed": "Да"})
    assert names(r["recommended"])[0] == "Газобетон"


def test_conditional_questions():
    qs = memory_questions()
    shown = [q["attribute"] for q in visible_questions(qs, {"element": "Кровля"})]
    assert "slope" in shown and "load" not in shown and "place" not in shown
