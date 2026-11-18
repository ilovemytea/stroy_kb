"""
Презентация к защите курсового проекта (docs/Презентация.pptx).

    py docs/build_slides.py
"""
import json
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMG = DOCS / "img"
sys.path.insert(0, str(ROOT))
from data import knowledge as K  # noqa: E402

EVAL = json.loads((DOCS / "evaluation.json").read_text(encoding="utf-8"))

BRICK = RGBColor(0xA8, 0x3F, 0x27)
BRICK_DARK = RGBColor(0x5E, 0x22, 0x15)
SAND = RGBColor(0xF4, 0xE7, 0xE0)
INK = RGBColor(0x22, 0x1E, 0x1B)
MUTED = RGBColor(0x6B, 0x63, 0x5B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SAGE = RGBColor(0x5B, 0x7F, 0x6A)
HEAD = "Cambria"
BODY = "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = 13.333, 7.5


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, spacing=None, name=None):
    """runs: строка или список абзацев; абзац — строка или список (текст, {опции})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        if spacing:
            para.space_after = Pt(spacing)
        parts = p if isinstance(p, list) else [(p, {})]
        for t, o in parts:
            r = para.add_run()
            r.text = t
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", italic)
            r.font.name = o.get("font", font)
            r.font.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def circle_num(slide, x, y, d, n, fill=BRICK, color=WHITE, size=18):
    c = box(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(size), True, BODY, color
    return c


def title(slide, t, sub=None):
    text(slide, 0.6, 0.45, 12.1, 0.8, t, size=34, font=HEAD, bold=True, color=INK, name="Title")
    if sub:
        text(slide, 0.6, 1.2, 12.1, 0.5, sub, size=16, color=MUTED)


def picture(slide, path, x, y, w=None, h=None, crop_h=None, frame=True):
    path = Path(path)
    if crop_h:
        im = Image.open(path)
        out = DOCS / "build" / f"{path.stem}_s{crop_h}.png"
        out.parent.mkdir(exist_ok=True)
        im.crop((0, 0, im.width, min(crop_h, im.height))).save(out)
        path = out
    im = Image.open(path)
    ar = im.height / im.width
    if w and h:            # вписать в рамку
        if ar > h / w:
            w = h / ar
        else:
            h = w * ar
    elif w:
        h = w * ar
    else:
        w = h / ar
    if frame:
        f = box(slide, x - 0.06, y - 0.06, w + 0.12, h + 0.12, WHITE, line=RGBColor(0xDD, 0xD5, 0xCE), radius=0.02)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h)), w, h


def footer(slide, n):
    text(slide, 0.6, 7.0, 8, 0.3, "Проектирование базы знаний по строительным материалам", size=10, color=MUTED)
    text(slide, 11.7, 7.0, 1.0, 0.3, str(n), size=10, color=MUTED, align=PP_ALIGN.RIGHT)


slide_no = 0


def new(dark=False):
    global slide_no
    slide_no += 1
    s = prs.slides.add_slide(BLANK)
    bg(s, BRICK_DARK if dark else WHITE)
    if not dark:
        footer(s, slide_no)
    return s


full = EVAL["full"]["by_kind"]
ms_max = max(v["ms"] for v in full.values())
N_ART, N_CON, N_REL, N_RULES = len(K.ARTICLES), len(K.CONCEPTS), len(K.RELATIONS), len(K.RULES)
N_SYN = sum(len(c[2]) for c in K.CONCEPTS)

# 1 ---------------------------------------------------------------- титул
s = new(dark=True)
for i in range(6):                     # кладка кирпичей — мотив презентации
    for j in range(3):
        off = 0.55 if i % 2 else 0
        box(s, 8.6 + j * 1.15 + off, 0.6 + i * 0.5, 1.05, 0.4, BRICK if (i + j) % 3 else RGBColor(0x8A, 0x33, 0x20),
            radius=0.1)
text(s, 0.8, 0.9, 7.5, 0.4, "КУРСОВОЙ ПРОЕКТ · ПРОЕКТИРОВАНИЕ БАЗ ЗНАНИЙ", size=14, color=SAND, bold=True)
text(s, 0.8, 1.45, 7.6, 2.9, "Проектирование базы знаний по строительным материалам", size=40, font=HEAD,
     bold=True, color=WHITE)
text(s, 0.8, 4.55, 7.4, 0.8, "Интеллектуальный поиск по слову, словосочетанию и вопросу до 15 слов",
     size=18, color=SAND, italic=True)
text(s, 0.8, 5.65, 7, 1.2, ["Выполнил: Дусов Алексей Эдуардович, 3 курс, «Искусственный интеллект»",
                           "Руководитель: Зайкова С.А.", "2026"], size=16, color=WHITE, spacing=4)
s.notes_slide.notes_text_frame.text = (
    "Здравствуйте. Тема моего курсового проекта — проектирование базы знаний по строительным материалам. "
    "Главная особенность — поиск, который понимает запрос на естественном языке: от одного слова до вопроса из 15 слов.")

# 2 ---------------------------------------------------------------- цель и задачи
s = new()
title(s, "Цель и задачи")
box(s, 0.6, 1.6, 4.6, 4.9, SAND, radius=0.05)
text(s, 0.95, 1.95, 4.0, 0.4, "ЦЕЛЬ", size=14, bold=True, color=BRICK)
text(s, 0.95, 2.4, 4.0, 3.8, "Разработать базу знаний о строительных материалах, которая в реальном времени отвечает "
     "на запросы пользователя — словом, словосочетанием или вопросом до 15 слов", size=20, color=INK, font=HEAD)
tasks = ["Проанализировать предметную область и аналоги",
         "Выбрать модели представления знаний, спроектировать БЗ",
         "Наполнить БЗ: статьи, онтология, правила",
         "Реализовать интеллектуальный поиск",
         "Реализовать экспертную систему подбора",
         "Разработать веб-интерфейс и редактор знаний",
         "Протестировать и исследовать характеристики"]
for i, t in enumerate(tasks):
    y = 1.65 + i * 0.68
    circle_num(s, 5.7, y, 0.46, i + 1, size=15)
    text(s, 6.35, y + 0.05, 6.4, 0.45, t, size=17, anchor=MSO_ANCHOR.MIDDLE)
s.notes_slide.notes_text_frame.text = "Цель и семь задач. Проект продолжает лабораторные работы 5–11: каталог из них вошёл в базу данных."

# 3 ---------------------------------------------------------------- проблема
s = new()
title(s, "Почему обычного поиска недостаточно")
rows = [("минвата", "В тексте написано «минеральная вата»", "Синонимы и сокращения онтологии"),
        ("гипсакартон", "Опечатка — ноль результатов", "Исправление по расстоянию правки"),
        ("кирпичами", "Другая словоформа", "Стемминг Snowball"),
        ("чем заменить газобетон", "Ищет слово «заменить»", "Намерение → связь «заменяет»"),
        ("какой утеплитель выбрать для бани чтобы он не горел", "Тонет в общих словах",
         "Покрытие запроса + быстрый ответ")]
text(s, 0.6, 1.55, 4.3, 0.4, "Запрос", size=14, bold=True, color=MUTED)
text(s, 5.1, 1.55, 3.6, 0.4, "Поиск по ключевым словам", size=14, bold=True, color=MUTED)
text(s, 8.9, 1.55, 3.9, 0.4, "Решение в «СтройМир»", size=14, bold=True, color=BRICK)
for i, (q, bad, good) in enumerate(rows):
    y = 2.0 + i * 0.92
    box(s, 0.6, y, 12.15, 0.78, SAND if i % 2 == 0 else WHITE, radius=0.12)
    text(s, 0.85, y, 4.1, 0.78, "«" + q + "»", size=16, bold=True, anchor=MSO_ANCHOR.MIDDLE, font=HEAD)
    text(s, 5.1, y, 3.6, 0.78, "✕  " + bad, size=15, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 8.9, y, 3.8, 0.78, "✓  " + good, size=15, color=SAGE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
s.notes_slide.notes_text_frame.text = (
    "Аналоги — сервисы баз знаний из обзора WEEEK, Springer Link, портал Всемирного банка, Oxford Text Archive — ищут по "
    "ключевым словам. Вот типичные запросы, на которых такой поиск ошибается, и как это решено в проекте.")

# 4 ---------------------------------------------------------------- модели знаний
s = new()
title(s, "Комбинированная модель представления знаний")
cards = [("Факты", "Реляционная модель", f"{N_ART} статей, каталог продукции из ЛР № 5–11",
          "kb.Material · kb.Tag · dbo.Product"),
         ("Онтология", "Семантическая сеть", f"{N_CON} понятий, {N_SYN} синонимов, {N_REL} связей 8 типов",
          "kb.Relation · рекурсивные функции"),
         ("Эвристики", "Продукции с CF", f"{N_RULES} правил «ЕСЛИ … ТО …», прямой вывод, схема MYCIN",
          "kb.Rule · kb.RuleCondition")]
for i, (h, m, d, t) in enumerate(cards):
    x = 0.6 + i * 4.15
    box(s, x, 1.7, 3.85, 4.6, SAND, radius=0.06)
    circle_num(s, x + 0.35, 2.05, 0.7, i + 1, size=22)
    text(s, x + 0.35, 3.0, 3.2, 0.5, h, size=26, bold=True, font=HEAD)
    text(s, x + 0.35, 3.55, 3.2, 0.4, m, size=16, color=BRICK, bold=True)
    text(s, x + 0.35, 4.1, 3.2, 1.3, d, size=17)
    text(s, x + 0.35, 5.55, 3.2, 0.5, t, size=13, color=MUTED, font="Courier New")
s.notes_slide.notes_text_frame.text = (
    "Знания разных типов хранятся в разных моделях. Факты — в таблицах, классификация, свойства и замены — в семантической "
    "сети, опыт специалистов — в продукционных правилах с коэффициентами уверенности. Всё хранится в SQL Server.")

# 5 ---------------------------------------------------------------- БД
s = new()
title(s, "Структура базы данных StroyMir_KB")
from PIL import ImageChops  # noqa: E402
im = Image.open(IMG / "d_kb_model.png").convert("RGB")
bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
(DOCS / "build").mkdir(exist_ok=True)
im.crop(bbox).save(DOCS / "build" / "kb_model_trim.png")
picture(s, LAB_ER := Path(r"C:\Users\admin\Desktop\лабы по БЗ\er_model_stroymir_kp.png"), 0.7, 1.6, w=5.6, h=4.9)
picture(s, DOCS / "build" / "kb_model_trim.png", 6.9, 1.6, w=5.8, h=3.4)
text(s, 6.9, 5.25, 5.8, 1.5, [[("Расширение ER-модели КП: ", {"bold": True}),
                               ("тег стал понятием онтологии, добавлены Связь, Правило, Условие, Вопрос. "
                                "Целостность — ключи и CHECK, триггер запрещает циклы в иерархии.", {})]], size=15)
s.notes_slide.notes_text_frame.text = (
    "Слева — ER-модель портала из лабораторных работ, справа — её расширение. Функция fn_ConceptAncestors рекурсивно "
    "находит предков понятия, fn_InheritedFacts — унаследованные знания. Триггер не даёт создать цикл в иерархии.")

# 6 ---------------------------------------------------------------- конвейер
s = new()
title(s, "Как обрабатывается запрос", "8 этапов, в среднем около 1 мс")
steps = [("Нормализация", "регистр, ё→е, ≤ 15 слов, вид запроса"),
         ("Опечатки", "Дамерау–Левенштейн: гипсакартон → гипсокартон"),
         ("Стемминг", "Snowball: кирпичами → кирпич"),
         ("Намерение", "«чем заменить» → связь «заменяет»"),
         ("Понятия", "«минеральная вата» — одно понятие"),
         ("Расширение", "синонимы ×0,7, виды понятия ×0,35"),
         ("Ранжирование", "BM25F × покрытие × близость × тег"),
         ("Ответ", "быстрый ответ, сниппеты, карточка понятия")]
for i, (h, d) in enumerate(steps):
    r, c = divmod(i, 4)
    x, y = 0.6 + c * 3.1, 1.95 + r * 2.45
    box(s, x, y, 2.85, 2.1, SAND if r == 0 else RGBColor(0xEC, 0xDB, 0xD2), radius=0.08)
    circle_num(s, x + 0.25, y + 0.25, 0.55, i + 1, size=16)
    text(s, x + 0.95, y + 0.3, 1.8, 0.5, h, size=18, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, y + 1.0, 2.4, 1.0, d, size=15)
s.notes_slide.notes_text_frame.text = (
    "Запрос проходит восемь этапов. Стеммер и исправление опечаток написаны с нуля, без внешних библиотек. "
    "Ключевой этап — распознавание понятий онтологии и расширение запроса синонимами и видами понятия.")

# 7 ---------------------------------------------------------------- выдача
s = new()
title(s, "Ответ на вопрос из 10 слов")
picture(s, IMG / "02_search_sentence.png", 0.7, 1.55, w=8.2, h=5.2, crop_h=1250)
text(s, 9.4, 1.6, 3.4, 5, [
    [("Вид запроса", {"bold": True, "color": BRICK})], "предложение, 10 слов",
    [("Понятия", {"bold": True, "color": BRICK})], "бетон, фундамент, газобетон",
    [("Быстрый ответ", {"bold": True, "color": BRICK})], "лучшее предложение базы знаний с источником",
    [("Карточка понятия", {"bold": True, "color": BRICK})], "определение, синонимы, связи онтологии",
], size=16, spacing=6)
s.notes_slide.notes_text_frame.text = (
    "Пример выдачи. Система определила, что это вопрос, нашла три понятия и показала быстрый ответ: для ленточного "
    "фундамента дома из газобетона достаточно бетона B20. Справа — карточка понятия со связями.")

# 8 ---------------------------------------------------------------- онтология
s = new()
title(s, "Онтология: семантическая сеть понятий")
picture(s, IMG / "07_graph.png", 0.7, 1.55, w=7.6, h=5.2, crop_h=1500)
for i, (n, l) in enumerate([(N_CON, "понятий в 6 категориях"), (N_REL, "связей 8 типов"), (N_SYN, "синонимов и сокращений")]):
    y = 1.7 + i * 1.25
    text(s, 8.9, y, 3.9, 0.7, str(n), size=44, bold=True, color=BRICK, font=HEAD)
    text(s, 8.9, y + 0.75, 3.9, 0.4, l, size=15, color=MUTED)
text(s, 8.9, 5.55, 3.9, 1.2, "Наследование: газобетон → ячеистый бетон → бетон, значит «изготавливается из цемента, "
     "песка и щебня»", size=14, italic=True)
s.notes_slide.notes_text_frame.text = (
    "Граф онтологии построен алгоритмом Фрюхтермана–Рейнгольда. Выделены связи газобетона. Благодаря иерархии "
    "работает наследование знаний и расширение запроса: по слову «утеплитель» находятся статьи о минвате и пенополистироле.")

# 9 ---------------------------------------------------------------- экспертная система
s = new()
title(s, "Экспертная система подбора материалов")
picture(s, IMG / "08_expert.png", 0.7, 1.55, w=6.2, h=5.2, crop_h=1600)
text(s, 7.5, 1.6, 5.3, 0.4, "Прямая цепочка рассуждений", size=20, bold=True, font=HEAD)
chain = ["building = Баня", "fire = Да (выведено)", "Пенополистирол: CF –0,89", "Минеральная вата: CF +0,93"]
for i, c in enumerate(chain):
    y = 2.25 + i * 0.7
    box(s, 7.5, y, 5.2, 0.55, SAND if i < 2 else (RGBColor(0xF6, 0xDE, 0xDA) if i == 2 else RGBColor(0xDF, 0xEE, 0xE4)),
        radius=0.2)
    text(s, 7.75, y, 4.8, 0.55, c, size=16, anchor=MSO_ANCHOR.MIDDLE, bold=i >= 2)
text(s, 7.5, 5.15, 5.2, 0.4, "Объединение уверенности (MYCIN):", size=15, bold=True)
text(s, 7.5, 5.55, 5.2, 1.2, ["CF = CF₁ + CF₂·(1 – CF₁) — оба > 0",
                              "CF = (CF₁ + CF₂) / (1 – min|CF|) — разных знаков"], size=14, font="Cambria Math")
s.notes_slide.notes_text_frame.text = (
    f"{N_RULES} правил. Ответы пользователя — исходные факты, правила выводят промежуточные факты и меняют уверенность "
    "в материалах. Каждый результат сопровождается трассой: какие правила сработали и как изменился коэффициент.")

# 10 --------------------------------------------------------------- интерфейс
s = new()
title(s, "Веб-интерфейс")
shots = [("03_search_typo.png", "Исправление опечатки", 1350), ("04_search_intent.png", "Намерение «из чего делают»", 1350),
         ("06_concept.png", "Страница понятия", 1350)]
for i, (f, cap, ch) in enumerate(shots):
    x = 0.6 + i * 4.15
    _, pw, ph = picture(s, IMG / f, x + 0.06, 1.75, w=3.85, crop_h=ch)
    text(s, x, 1.75 + ph + 0.2, 3.95, 0.4, cap, size=15, bold=True, align=PP_ALIGN.CENTER)
text(s, 0.6, 5.95, 12.1, 0.9, "Также: граф онтологии, каталог продукции, страница статистики с замером скорости, "
     "редактор знаний — новая статья сразу доступна в поиске", size=16, color=MUTED, align=PP_ALIGN.CENTER)
s.notes_slide.notes_text_frame.text = "Интерфейс работает без Интернета: Flask, свой CSS и JavaScript, граф на SVG. Адаптирован под телефон."

# 11 --------------------------------------------------------------- качество
s = new()
title(s, "Исследование: вклад каждого механизма", "24 контрольных запроса, доля запросов с релевантной статьёй на 1-м месте (P@1)")
cd = CategoryChartData()
cd.categories = ["Слово", "Словосочетание", "Предложение"]
for key in ("full", "no_spell", "no_stem", "no_onto"):
    v = EVAL[key]
    cd.add_series(v["label"], [round(v["by_kind"][k]["P@1"], 2) for k in ("слово", "словосочетание", "предложение")])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.8), Inches(8.4), Inches(4.9), cd)
ch = gf.chart
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.BOTTOM
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
ch.legend.font.name = BODY
colors = [BRICK, RGBColor(0xD9, 0x8C, 0x6E), RGBColor(0xB9, 0xAE, 0xA4), RGBColor(0x6B, 0x63, 0x5B)]
plot = ch.plots[0]
plot.gap_width = 60
plot.has_data_labels = True
plot.data_labels.number_format = "0.00"
plot.data_labels.number_format_is_linked = False
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
plot.data_labels.font.size = Pt(11)
plot.data_labels.font.color.rgb = INK
for ser, c in zip(plot.series, colors):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = c
va = ch.value_axis
va.maximum_scale, va.minimum_scale = 1.1, 0
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xE0, 0xDA)
va.tick_labels.font.size = Pt(12)
va.tick_labels.font.color.rgb = MUTED
va.format.line.fill.background()
ch.category_axis.tick_labels.font.size = Pt(14)
ch.category_axis.tick_labels.font.color.rgb = INK
no = EVAL["no_onto"]["by_kind"]
text(s, 9.5, 1.9, 3.3, 0.8, "0,50", size=48, bold=True, color=BRICK, font=HEAD)
text(s, 9.5, 2.75, 3.3, 1.0, "P@1 для одиночных слов без синонимов и онтологии (было 1,00)", size=15)
text(s, 9.5, 4.0, 3.3, 2.5, "«газоблок», «рубероид», «самонивелир», «ЖБИ» — этих слов нет в статьях, их находит "
     "только онтология", size=15, color=MUTED, italic=True)
s.notes_slide.notes_text_frame.text = (
    "Абляционный эксперимент: отключали механизмы по одному. Полная система — 1,0 на всех видах запросов. Сильнее всего "
    "качество падает без онтологии. Стемминг важен для словосочетаний, исправление опечаток — для одиночных слов. "
    "Ограничение: набор небольшой, оценка оптимистична.")

# 12 --------------------------------------------------------------- скорость и тесты
s = new()
title(s, "Скорость и надёжность")
stats = [(f"≈{ms_max:.1f} мс".replace(".", ","), "время ответа на запрос-предложение", "требование — 100 мс"),
         ("42 / 42", "автоматических теста пройдены", "поиск, вывод, веб, БД"),
         ("1,00", "P@1 на 24 контрольных запросах", "8 слов · 8 словосочетаний · 8 вопросов")]
for i, (big, l1, l2) in enumerate(stats):
    x = 0.6 + i * 4.15
    box(s, x, 1.8, 3.85, 3.4, SAND, radius=0.06)
    text(s, x + 0.35, 2.1, 3.2, 1.2, big, size=50, bold=True, color=BRICK, font=HEAD)
    text(s, x + 0.35, 3.35, 3.2, 0.9, l1, size=17, bold=True)
    text(s, x + 0.35, 4.35, 3.2, 0.6, l2, size=14, color=MUTED)
text(s, 0.6, 5.6, 12.1, 1.0, "Скорость обеспечивает инвертированный индекс в оперативной памяти: он строится из базы "
     "за ~20 мс и перестраивается после каждой правки в редакторе знаний", size=16, color=MUTED)
s.notes_slide.notes_text_frame.text = "Скорость и тесты. Время ответа — единицы миллисекунд, на два порядка меньше требования."

# 13 --------------------------------------------------------------- заключение
s = new(dark=True)
text(s, 0.8, 0.6, 11.5, 0.8, "Результаты", size=36, bold=True, font=HEAD, color=WHITE)
res = ["Спроектирована комбинированная БЗ: факты, онтология, продукционные правила",
       f"Наполнена: {N_ART} статей, {N_CON} понятий, {N_REL} связей, {N_RULES} правил",
       "Поиск по слову, словосочетанию и вопросу до 15 слов: морфология, опечатки, синонимы, намерения",
       "Экспертная система с объяснением вывода",
       "Веб-интерфейс, граф онтологии, редактор знаний",
       "P@1 = 1,0 на контрольном наборе, ответ ≈ 1 мс"]
for i, r in enumerate(res):
    y = 1.65 + i * 0.78
    circle_num(s, 0.8, y, 0.5, i + 1, fill=BRICK, size=15)
    text(s, 1.55, y, 10.9, 0.5, r, size=19, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.8, 6.55, 11.5, 0.5, "Развитие: синонимы из журнала пустых запросов, векторный поиск, расчёт толщины утеплителя",
     size=15, italic=True, color=SAND)
s.notes_slide.notes_text_frame.text = "Цель достигнута, все задачи решены. Спасибо за внимание, готов ответить на вопросы."

# 14 --------------------------------------------------------------- спасибо
s = new(dark=True)
text(s, 0.8, 2.6, 11.7, 1.2, "Спасибо за внимание!", size=48, bold=True, font=HEAD, color=WHITE, align=PP_ALIGN.CENTER)
text(s, 0.8, 3.9, 11.7, 0.6, "Демонстрация: py app.py → http://localhost:5000", size=18, color=SAND, align=PP_ALIGN.CENTER)

out = DOCS / "Презентация.pptx"
prs.save(out)
print("saved", out, slide_no, "slides")
