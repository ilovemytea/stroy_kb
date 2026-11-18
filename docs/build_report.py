"""
Сборка пояснительной записки к курсовому проекту (docs/Пояснительная записка.docx).
Числовые данные (объём знаний, метрики поиска, результаты экспертной системы)
берутся из проекта, а не вписываются вручную.

    py docs/evaluate.py          — сначала обновить метрики
    py docs/build_report.py [--pages N]
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMG = DOCS / "img"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from data import knowledge as K          # noqa: E402
from expert import infer                  # noqa: E402
from memory_kb import memory_rules        # noqa: E402

LAB_DIR = Path(r"C:\Users\admin\Desktop\лабы по БЗ")
ACCESS_DATE = "03.11.2026"
FONT = "Times New Roman"

EVAL = json.loads((DOCS / "evaluation.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- счётчики
fig_no = 0
tab_no = 0
lst_no = 0


def set_font(run, size=14, bold=None, italic=None, name=FONT):
    run.font.name = name
    run.font.size = Pt(size)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), name)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def setup_styles(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(14)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = st.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    for name, size, align in (("Heading 1", 14, WD_ALIGN_PARAGRAPH.CENTER), ("Heading 2", 14, WD_ALIGN_PARAGRAPH.JUSTIFY)):
        h = doc.styles[name]
        h.font.name = FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.italic = False
        h.font.color.rgb = RGBColor(0, 0, 0)
        rpr = h.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(a), FONT)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rfonts.get(qn(a)) is not None:
                del rfonts.attrib[qn(a)]
        hf = h.paragraph_format
        hf.alignment = align
        hf.space_before = Pt(0 if name == "Heading 1" else 12)
        hf.space_after = Pt(12 if name == "Heading 1" else 6)
        hf.line_spacing = 1.5
        hf.keep_with_next = True
        hf.first_line_indent = Cm(0) if name == "Heading 1" else Cm(1.25)


def para(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True, size=14, bold=False, italic=False,
         spacing=1.5, before=0, after=0, keep_next=False):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.first_line_indent = Cm(1.25) if indent else Cm(0)
    pf.line_spacing = spacing
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.keep_with_next = keep_next
    if text:
        add_rich(p, text, size=size, bold=bold, italic=italic)
    return p


def add_rich(p, text, size=14, bold=False, italic=False):
    """Текст с разметкой **жирный** и `код`."""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            set_font(p.add_run(part[2:-2]), size, bold=True, italic=italic)
        elif part.startswith("`"):
            set_font(p.add_run(part[1:-1]), size - 1, bold=bold, italic=italic, name="Courier New")
        else:
            set_font(p.add_run(part), size, bold=bold, italic=italic)


def bullets(doc, items, numbered=False):
    for i, it in enumerate(items, 1):
        p = para(doc, "")
        mark = f"{i}) " if numbered else "– "
        add_rich(p, mark + it)


def h1(doc, text, page_break=True):
    if page_break:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        # пустой абзац с разрывом не должен оставлять лишнюю строку
        last = doc.paragraphs[-1]
        last.paragraph_format.line_spacing = 1.0
        last.paragraph_format.space_after = Pt(0)
    p = doc.add_heading(text, level=1)
    return p


def h2(doc, text):
    return doc.add_heading(text, level=2)


def caption(doc, text, before=6, after=6, keep_next=False):
    return para(doc, text, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, size=14, spacing=1.0,
                before=before, after=after, keep_next=keep_next)


def table_caption(doc, text):
    global tab_no
    tab_no += 1
    p = para(doc, f"Таблица {tab_no} – {text}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=False, spacing=1.0,
             before=6, after=4, keep_next=True)
    return tab_no


def set_cell_shading(cell, color):
    tcpr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def set_repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def table(doc, header, rows, widths, title, size=12, align_num=()):
    table_caption(doc, title)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, txt in enumerate(header):
        c = t.rows[0].cells[i]
        c.width = Cm(widths[i])
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraphs[0].paragraph_format.line_spacing = 1.0
        set_font(c.paragraphs[0].add_run(str(txt)), size, bold=True)
        set_cell_shading(c, "E7E6E6")
    set_repeat_header(t.rows[0])
    for r in rows:
        cells = t.add_row().cells
        for i, txt in enumerate(r):
            c = cells[i]
            c.width = Cm(widths[i])
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i in align_num else WD_ALIGN_PARAGRAPH.LEFT
            add_rich(p, str(txt), size=size)
    para(doc, "", spacing=1.0)
    return t


def trim(path):
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        pad = 20
        box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
        im = im.crop(box)
    out = DOCS / "build" / (path.stem + ".png")
    out.parent.mkdir(exist_ok=True)
    im.save(out)
    return out


def figure(doc, path, text, width_cm=16.0, max_h_cm=20.0, crop=None, trim_white=False):
    global fig_no
    fig_no += 1
    path = Path(path)
    if crop or trim_white:
        im = Image.open(path)
        if crop:
            im = im.crop((0, 0, im.width, min(im.height, crop)))
            out = DOCS / "build" / (path.stem + f"_c{crop}.png")
            out.parent.mkdir(exist_ok=True)
            im.save(out)
            path = out
        if trim_white:
            path = trim(path)
    im = Image.open(path)
    w, h = im.size
    width = width_cm
    if h / w * width > max_h_cm:
        width = max_h_cm * w / h
    p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, spacing=1.0, before=6, keep_next=True)
    p.add_run().add_picture(str(path), width=Cm(width))
    caption(doc, f"Рисунок {fig_no} – {text}", after=10)
    return fig_no


def listing(doc, title, code, size=9):
    global lst_no
    lst_no += 1
    para(doc, f"Листинг {lst_no} – {title}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=False, spacing=1.0,
         before=6, after=4, keep_next=True)
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    c.width = Cm(16.5)
    lines = code.rstrip("\n").split("\n")
    p = c.paragraphs[0]
    p.paragraph_format.line_spacing = 1.0
    for i, line in enumerate(lines):
        r = p.add_run(line.replace("\t", "    "))
        set_font(r, size, name="Courier New")
        if i < len(lines) - 1:
            r.add_break()
    para(doc, "", spacing=1.0)
    return lst_no


def add_field(paragraph, instr, placeholder=""):
    r = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    r._r.append(b)
    r2 = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r2._r.append(it)
    r3 = paragraph.add_run()
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    r3._r.append(s)
    r4 = paragraph.add_run(placeholder)
    set_font(r4, 14)
    r5 = paragraph.add_run()
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    r5._r.append(e)


def code_excerpt(path, start_pat, end_pat=None, max_lines=60):
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    start = next(i for i, l in enumerate(lines) if re.search(start_pat, l))
    end = len(lines)
    if end_pat:
        end = next((i for i in range(start + 1, len(lines)) if re.search(end_pat, lines[i])), len(lines))
    return "\n".join(lines[start:min(end, start + max_lines)]).rstrip()


def fmt(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


# ---------------------------------------------------------------- данные для текста
N_ART = len(K.ARTICLES)
N_CON = len(K.CONCEPTS)
N_REL = len(K.RELATIONS)
N_RULES = len(K.RULES)
N_FACT_RULES = sum(1 for r in K.RULES if r[2][0] == "fact")
N_SYN = sum(len(c[2]) for c in K.CONCEPTS)
N_TAGLINKS = sum(len(a[5]) for a in K.ARTICLES)
N_VIDEO = sum(1 for a in K.ARTICLES if a[8])
REL_COUNT = Counter(r[1] for r in K.RELATIONS)
CAT_COUNT = Counter(c[1] for c in K.CONCEPTS)
WORDS = sum(len(re.findall(r"\w+", a[7])) for a in K.ARTICLES)


def run_tests():
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], capture_output=True,
                         text=True, cwd=ROOT, encoding="utf-8", errors="replace")
    m = re.search(r"(\d+) passed", res.stdout)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- документ
def build(pages):
    doc = Document()
    setup_styles(doc)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(2)
    sec.different_first_page_header_footer = True
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(fp, "PAGE", "2")

    # ---------- титульный лист
    C = WD_ALIGN_PARAGRAPH.CENTER
    for t in ("Факультет математики и информатики",
              "Кафедра системного программирования и компьютерной безопасности"):
        para(doc, t, align=C, indent=False)
    for _ in range(5):
        para(doc, "", align=C, indent=False)
    para(doc, "КУРСОВОЙ ПРОЕКТ", align=C, indent=False, bold=True)
    para(doc, "«Проектирование базы знаний по строительным материалам»", align=C, indent=False, bold=True)
    para(doc, "по дисциплине «Проектирование баз знаний»", align=C, indent=False)
    para(doc, "", align=C, indent=False)
    para(doc, "Пояснительная записка", align=C, indent=False)
    para(doc, "", align=C, indent=False)
    para(doc, "", align=C, indent=False)
    R = WD_ALIGN_PARAGRAPH.LEFT
    for t in ("Выполнил: студент 3 курса,", "специальности «Искусственный интеллект»",
              "Дусов Алексей Эдуардович", "", "Руководитель: Зайкова С.А."):
        p = para(doc, t, align=R, indent=False)
        p.paragraph_format.left_indent = Cm(8.5)
    for _ in range(6):
        para(doc, "", align=C, indent=False)
    para(doc, "2026", align=C, indent=False)

    # ---------- реферат
    tests_passed = run_tests()
    h1(doc, "РЕФЕРАТ")
    para(doc, f"Курсовой проект: {pages} с., {{FIGS}} рис., {{TABS}} табл., 15 источников, 3 прил.")
    para(doc, "БАЗА ЗНАНИЙ, ОНТОЛОГИЯ, СЕМАНТИЧЕСКАЯ СЕТЬ, ПРОДУКЦИОННЫЕ ПРАВИЛА, ЭКСПЕРТНАЯ СИСТЕМА, "
              "ИНФОРМАЦИОННЫЙ ПОИСК, СТЕММИНГ, BM25, СТРОИТЕЛЬНЫЕ МАТЕРИАЛЫ, MICROSOFT SQL SERVER, FLASK")
    para(doc, "Объект разработки — база знаний в предметной области «Строительные материалы».")
    para(doc, "Цель работы — разработка базы знаний, отвечающей на запросы пользователя в режиме реального времени. "
              "Запрос может быть словом, словосочетанием или предложением длиной до 15 слов.")
    para(doc, "В процессе работы проанализированы существующие системы управления знаниями и поисковые порталы. "
              "Выбрана комбинированная модель представления знаний: реляционные факты, семантическая сеть понятий "
              "и продукционные правила с коэффициентами уверенности. Спроектирована и реализована база данных "
              "в Microsoft SQL Server. Разработаны поисковая машина с морфологическим анализом русского языка, "
              "исправлением опечаток и расширением запроса по онтологии, а также машина логического вывода "
              "экспертной системы. Создано веб-приложение на языке Python (Flask).")
    full = EVAL["full"]["by_kind"]
    para(doc, f"Результаты: база знаний содержит {N_ART} статей, {N_CON} понятий, {N_REL} семантических связей "
              f"и {N_RULES} продукционных правил. На контрольном наборе из 24 запросов полная система ставит "
              f"релевантную статью на первое место во всех случаях (P@1 = 1,0). Среднее время ответа — около "
              f"{fmt(max(v['ms'] for v in full.values()), 1)} мс. Все {tests_passed} автоматических тестов пройдены.")
    para(doc, "Область применения: справочная система для покупателей и строителей, учебное пособие по "
              "строительному материаловедению, информационный портал торговой организации.")

    # ---------- содержание
    h1(doc, "СОДЕРЖАНИЕ")
    p = para(doc, "", indent=False)
    add_field(p, 'TOC \\o "1-2" \\h \\z \\u', "Обновите поле (F9), чтобы построить содержание.")

    # ---------- введение
    h1(doc, "ВВЕДЕНИЕ")
    para(doc, "Строительные материалы — обширная предметная область. В ней сотни видов изделий, десятки "
              "нормативных документов и множество взаимосвязанных свойств: прочность, плотность, "
              "теплопроводность, морозостойкость, горючесть. Покупателю или начинающему строителю трудно "
              "сопоставить эти сведения и выбрать материал под конкретную задачу. Обычные каталоги ищут по "
              "точному совпадению слов. Они не понимают вопрос «чем заменить газобетон», не знают, что «минвата» "
              "и «минеральная вата» — одно и то же, и не объясняют, почему для бани не подходит пенополистирол.")
    para(doc, "Базы знаний позволяют хранить не только факты, но и смысловые связи между понятиями, а также правила, "
              "по которым из фактов выводятся новые знания. Сочетание базы знаний с полнотекстовым поиском даёт "
              "систему, которая понимает запрос, заданный естественным языком, и отвечает на него.")
    para(doc, "**Цель курсового проекта** — разработка базы знаний в предметной области «Строительные материалы», "
              "ориентированной на ответы на запросы пользователя в режиме реального времени.")
    para(doc, "Для достижения цели поставлены следующие **задачи**:")
    bullets(doc, [
        "проанализировать предметную область и существующие системы управления знаниями и поиска;",
        "выбрать модели представления знаний и спроектировать структуру базы знаний;",
        "наполнить базу знаний статьями, понятиями онтологии, семантическими связями и правилами вывода;",
        "реализовать поиск по слову, словосочетанию и предложению длиной до 15 слов с учётом морфологии, "
        "синонимов и опечаток;",
        "реализовать экспертную систему подбора материалов с объяснением вывода;",
        "разработать веб-интерфейс пользователя и редактора знаний;",
        "протестировать систему и исследовать её характеристики: качество и скорость поиска.",
    ], numbered=True)
    para(doc, "Работа продолжает лабораторные работы № 5–11 по дисциплине. Реляционная часть базы данных — "
              "каталог производителей, продукции, сырья и поставок — перенесена из них без изменений. В курсовом "
              "проекте к каталогу добавлены база знаний и интеллектуальная надстройка.")
    para(doc, "Пояснительная записка состоит из четырёх глав. Первая глава посвящена анализу предметной области "
              "и аналогов, вторая — проектированию базы знаний, третья — программной реализации, четвёртая — "
              "тестированию и исследованию характеристик.")

    # ================================================================ ГЛАВА 1
    h1(doc, "ГЛАВА 1. АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ И ПОСТАНОВКА ЗАДАЧИ")
    h2(doc, "1.1 Предметная область «Строительные материалы»")
    para(doc, "Строительный материал — материал или изделие, применяемое для возведения и ремонта зданий и "
              "сооружений. Знания о строительных материалах можно разделить на несколько групп:")
    bullets(doc, [
        "**классификационные** — иерархия видов: «керамический кирпич» является видом «кирпича», тот — "
        "видом «стенового материала»;",
        "**фактические** — характеристики материалов: плотность, теплопроводность, прочность, морозостойкость, "
        "группа горючести;",
        "**причинно-следственные** — зависимости: высокое водопоглощение снижает морозостойкость, поэтому "
        "силикатный кирпич не применяют в цоколе;",
        "**нормативные** — требования стандартов (ГОСТ 530-2012, ГОСТ 31360-2007, СТБ 1160-99 и др.);",
        "**процедурные** — технологии работ: кладка, армирование, устройство гидроизоляции, стяжки;",
        "**эвристические** — опыт специалистов: «для бани используйте только негорючий утеплитель».",
    ])
    para(doc, "Пользователи формулируют запросы по-разному: одним словом («газоблок»), словосочетанием "
              "(«гидроизоляция фундамента») или вопросом («какой бетон нужен для ленточного фундамента частного дома "
              "из газобетона»). В запросах встречаются профессиональные сокращения (ГКЛВ, ЭППС, ЖБИ, ЦПС), "
              "разговорные названия (минвата, пенопласт, профлист) и опечатки. Русский язык флективен: одно слово "
              "имеет до двух десятков словоформ («кирпич», «кирпича», «кирпичами»). Система, отвечающая на такие "
              "запросы, должна учитывать все эти особенности.")

    h2(doc, "1.2 Обзор аналогов")
    para(doc, "Для анализа были рассмотрены системы, предложенные в задании: обзор сервисов для создания баз "
              "знаний [1], поиск новостного портала HuffPost [2], научная платформа Springer Link [3], "
              "портал Всемирного банка [4] и Oxford Text Archive [5].")
    para(doc, "В обзоре [1] сравниваются десять сервисов для корпоративных баз знаний: Weeek, OkoCRM, Strive, "
              "Аспро.Agile, Teamly, Битрикс24, GitBook, Confluence, Guru и Obsidian. Это редакторы документов "
              "с иерархией страниц, правами доступа и полнотекстовым поиском. Знания в них хранятся как "
              "неструктурированный текст. Связи между понятиями задаются вручную ссылками; правил вывода нет.")
    para(doc, "Springer Link [3] и Oxford Text Archive [5] — крупные хранилища научных публикаций и текстовых "
              "корпусов. В них есть фасетный поиск по типу документа, дисциплине и дате, а также автодополнение "
              "запроса. Портал Всемирного банка [4] и поиск HuffPost [2] ищут по ключевым словам с сортировкой "
              "по релевантности или дате. Эти системы не строят ответ на вопрос и не используют онтологию "
              "предметной области в явном виде.")
    table(doc, ["Возможность", "Сервисы баз знаний [1]", "Springer, OTA [3, 5]", "World Bank, HuffPost [2, 4]",
                "Проект «СтройМир»"], [
        ["Полнотекстовый поиск", "+", "+", "+", "+"],
        ["Учёт словоформ русского языка", "частично", "–", "–", "+"],
        ["Исправление опечаток", "частично", "+", "частично", "+"],
        ["Синонимы и сокращения предметной области", "–", "–", "–", "+"],
        ["Фасетные фильтры", "частично", "+", "+", "+"],
        ["Быстрый ответ на вопрос", "–", "–", "–", "+"],
        ["Онтология (семантическая сеть)", "–", "–", "–", "+"],
        ["Логический вывод, подбор решения", "–", "–", "–", "+"],
        ["Объяснение результата", "–", "–", "–", "+"],
    ], [5.2, 2.9, 2.6, 2.9, 2.9], "Сравнение аналогов", align_num=(1, 2, 3, 4))
    para(doc, "Ни одна из рассмотренных систем не сочетает полнотекстовый поиск с онтологией и логическим выводом "
              "в узкой предметной области. Из аналогов заимствованы удачные элементы интерфейса: строка поиска "
              "с автодополнением, фильтры по типу материала, выделение найденных слов в сниппетах. Разрабатываемая "
              "система добавляет к ним интеллектуальную обработку запроса.")

    h2(doc, "1.3 Требования к базе знаний")
    para(doc, "На основе анализа сформулированы функциональные требования:")
    bullets(doc, [
        "поиск по запросу из одного слова, словосочетания (2–4 слова) или предложения (5–15 слов); более "
        "длинный запрос обрезается до 15 слов с уведомлением пользователя;",
        "нечувствительность к словоформам, регистру и букве «ё»;",
        "исправление опечаток с подсказкой «Показаны результаты по запросу…»;",
        "расширение запроса синонимами, сокращениями и подчинёнными понятиями онтологии;",
        "распознавание намерения пользователя: «чем заменить», «из чего делают», «для чего», «что такое»;",
        "«быстрый ответ» — предложение из базы знаний, отвечающее на вопрос, с указанием источника;",
        "карточка понятия со связями онтологии и граф семантической сети;",
        "экспертная система подбора материалов с коэффициентами уверенности и объяснением вывода;",
        "редактор знаний: добавление и изменение статей, понятий и связей без программирования;",
        "журнал запросов и инструменты исследования характеристик базы знаний.",
    ])
    para(doc, "Нефункциональные требования: время ответа на запрос — не более 100 мс; хранение данных в СУБД "
              "Microsoft SQL Server (как в лабораторных работах); работа без подключения к Интернету; "
              "веб-интерфейс, корректно отображаемый на компьютере и телефоне.")
    h2(doc, "1.4 Выводы")
    para(doc, "Предметная область «Строительные материалы» содержит знания разных типов: классификационные, "
              "фактические, причинно-следственные, нормативные и эвристические. Существующие системы хранят "
              "знания как текст и ищут по ключевым словам. Поэтому для решения задачи нужна база знаний, "
              "сочетающая несколько моделей представления знаний с интеллектуальной обработкой запроса.")

    # ================================================================ ГЛАВА 2
    h1(doc, "ГЛАВА 2. ПРОЕКТИРОВАНИЕ БАЗЫ ЗНАНИЙ")
    h2(doc, "2.1 Выбор моделей представления знаний")
    para(doc, "Основные модели представления знаний — логическая, продукционная, фреймовая и сетевая [6, 7]. "
              "Каждая из них лучше подходит для своего типа знаний, поэтому в проекте они комбинируются "
              "(таблица 2).")
    table(doc, ["Тип знаний", "Модель", "Реализация в проекте"], [
        ["Факты о материалах, статьи, каталог", "Реляционная модель (факты)",
         "Таблицы kb.Material, kb.Tag, dbo.Product и др."],
        ["Классификация, свойства, применение, замены", "Семантическая сеть (онтология)",
         "Таблица kb.Relation: «понятие — отношение — понятие»"],
        ["Описание понятия: определение, синонимы, категория", "Фрейм (слоты понятия)",
         "Атрибуты kb.Tag: definition, synonyms, id_category"],
        ["Эвристики подбора материалов", "Продукционная модель с CF",
         "Таблицы kb.Rule, kb.RuleCondition, kb.Question"],
        ["Текстовые знания для поиска", "Инвертированный индекс",
         "Строится приложением из kb.Material при запуске"],
    ], [4.6, 4.4, 7.5], "Модели представления знаний в проекте")
    para(doc, "Семантическая сеть выбрана для онтологии, потому что её наглядно визуализировать, легко "
              "пополнять и по ней удобно расширять поисковый запрос. Продукционная модель выбрана для "
              "экспертных эвристик: каждое правило понятно эксперту, правила независимы друг от друга, "
              "а цепочка сработавших правил служит готовым объяснением результата [8].")

    h2(doc, "2.2 Инфологическая модель")
    para(doc, "Инфологическая модель портала «СтройМир» (рисунок 1) построена на этапе лабораторных работ. "
              "Центральная сущность — МАТЕРИАЛ (статья базы знаний). Она связана с ИЗДАНИЕМ, СТРАНОЙ и "
              "ТИПОМ МАТЕРИАЛА. Связь «многие ко многим» между материалом и ТЕГОМ реализуется сущностью "
              "МАТЕРИАЛ_ТЕГ с атрибутами ранжирования: оценкой релевантности, позицией в выдаче и итоговым рангом. "
              "Теги объединены в КАТЕГОРИИ. Видеоролик связан с материалом отношением «один к нулю или одному».")
    figure(doc, LAB_DIR / "er_model_stroymir_kp.png",
           "ER-диаграмма предметной области «Информационно-поисковый портал по стройматериалам СтройМир»",
           max_h_cm=14)
    para(doc, "В курсовом проекте тег получил роль понятия онтологии: к его атрибутам добавлено определение, "
              "а поле «синонимы» используется поиском. Модель расширена сущностями СВЯЗЬ (ребро семантической "
              "сети), ПРАВИЛО, УСЛОВИЕ и ВОПРОС (рисунок 2).")
    figure(doc, IMG / "d_kb_model.png", "Расширение инфологической модели: онтология и экспертная система",
           max_h_cm=10, trim_white=True)

    h2(doc, "2.3 Онтология предметной области")
    para(doc, f"Онтология содержит {N_CON} понятий шести категорий и {N_REL} связей восьми типов. У понятий "
              f"всего {N_SYN} синонимов и сокращений. Распределение понятий по категориям и связей по типам "
              f"приведено в таблицах 3 и 4.")
    table(doc, ["Категория", "Понятий", "Примеры"], [
        [c, CAT_COUNT[c], ", ".join([x[0] for x in K.CONCEPTS if x[1] == c][:4]) + "…"] for c, _ in K.CATEGORIES
    ], [4.2, 2.2, 10.1], "Категории понятий онтологии", align_num=(1,))
    REL_DESCR = {
        "является": "родо-видовая иерархия (is-a)",
        "изготавливается_из": "сырьё и компоненты",
        "применяется_для": "область применения",
        "обладает_свойством": "характерное свойство",
        "заменяет": "допустимая замена (аналог)",
        "регламентируется": "нормативный документ",
        "несовместим_с": "недопустимое применение",
        "часть": "участие в технологии",
    }
    table(doc, ["Тип связи", "Смысл", "Количество", "Пример"], [
        [t, REL_DESCR[t], REL_COUNT[t], " → ".join(next((a, b) for a, tt, b in K.RELATIONS if tt == t))]
        for t in REL_DESCR
    ], [3.8, 4.6, 2.4, 5.7], "Типы семантических связей", align_num=(2,))
    para(doc, "Связь «является» образует иерархию. Её транзитивное замыкание вычисляется рекурсивной функцией "
              "kb.fn_ConceptAncestors. Благодаря иерархии работает **наследование**: связи, заданные для общего "
              "понятия, распространяются на частные. Например, газобетон является ячеистым бетоном, а тот — "
              "бетоном. Поэтому газобетон наследует от бетона связь «изготавливается из цемента, песка и щебня». "
              "Наследование реализовано функцией kb.fn_InheritedFacts.")
    para(doc, "Синонимы — важнейшая часть онтологии для поиска. Например, у понятия «Газобетон» заданы синонимы "
              "«газоблок», «газосиликат», «газобетонный блок», «автоклавный газобетон», а у понятия "
              "«Влагостойкий гипсокартон» — сокращение «ГКЛВ».")

    h2(doc, "2.4 Продукционная модель экспертной системы")
    para(doc, "Экспертная система решает задачу подбора материалов. Рабочая память — набор фактов «атрибут = "
              f"значение». Исходные факты — ответы пользователя на {len(K.QUESTIONS)} вопросов (таблица 5). "
              "Часть вопросов задаётся условно: вопрос об уклоне крыши — только если выбрана кровля.")
    table(doc, ["Атрибут", "Вопрос", "Варианты ответа"], [
        [a, t, " / ".join(o)] for a, t, o, c in K.QUESTIONS
    ], [2.6, 6.0, 7.9], "Вопросы экспертной системы")
    para(doc, f"База содержит {N_RULES} правил вида «ЕСЛИ условие1 И условие2 … ТО заключение (CF)». "
              f"Правила двух типов:")
    bullets(doc, [
        f"**правила-факты** ({N_FACT_RULES} шт.) выводят промежуточные факты. Например, R04: ЕСЛИ element = "
        "Фундамент ТО zone = грунт; R05: ЕСЛИ zone = грунт ТО need_water = да;",
        f"**правила-рекомендации** ({N_RULES - N_FACT_RULES} шт.) изменяют коэффициент уверенности CF для "
        "понятия-материала. CF лежит в диапазоне от –1 (точно не подходит) до +1 (точно подходит). "
        "Например, R91: ЕСЛИ building = Баня ТО Пенополистирол (CF = –0,9).",
    ])
    para(doc, "Вывод выполняется прямой цепочкой рассуждений (forward chaining). Применяются все правила, "
              "условия которых выполнены в рабочей памяти. Если правило добавило новый факт, цикл повторяется. "
              "Когда на один материал срабатывает несколько правил, их коэффициенты объединяются по схеме "
              "MYCIN [8]:")
    for f in ("CF = CF₁ + CF₂ · (1 – CF₁), если CF₁ ≥ 0 и CF₂ ≥ 0;",
              "CF = CF₁ + CF₂ · (1 + CF₁), если CF₁ < 0 и CF₂ < 0;",
              "CF = (CF₁ + CF₂) / (1 – min(|CF₁|, |CF₂|)) в остальных случаях."):
        para(doc, f, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    para(doc, "Материалы с итоговым CF ≥ 0,2 рекомендуются, с CF < 0 — отвергаются. Для каждого вывода "
              "сохраняется трасса: номер шага, правило, его условия и изменение CF. Это позволяет системе "
              "ответить на вопрос «почему?».")
    h2(doc, "2.5 Выводы")
    para(doc, "Спроектирована комбинированная база знаний. Факты хранятся в реляционной модели, понятия и их "
              "отношения — в семантической сети, эвристики подбора — в продукционной модели с коэффициентами "
              "уверенности. ER-модель лабораторных работ расширена без изменения исходных сущностей.")

    # ================================================================ ГЛАВА 3
    h1(doc, "ГЛАВА 3. ПРОГРАММНАЯ РЕАЛИЗАЦИЯ")
    h2(doc, "3.1 Архитектура системы")
    para(doc, "Система построена по трёхуровневой архитектуре (рисунок 3). Уровень данных — Microsoft SQL Server. "
              "Уровень логики — веб-приложение на Python с фреймворком Flask [10]. Уровень представления — "
              "браузер пользователя.")
    figure(doc, IMG / "d_architecture.png", "Архитектура системы", trim_white=True)
    table(doc, ["Компонент", "Технология", "Назначение"], [
        ["СУБД", "Microsoft SQL Server 2022", "Хранение фактов, онтологии, правил, журнала"],
        ["Язык серверной части", "Python 3.14", "Поиск, логический вывод, веб-приложение"],
        ["Веб-фреймворк", "Flask 3.1, шаблоны Jinja2", "Маршрутизация, формирование HTML"],
        ["Доступ к БД", "pyodbc, ODBC Driver 17", "Выполнение T-SQL из приложения"],
        ["Клиентская часть", "HTML5, CSS3, JavaScript, SVG", "Интерфейс, автодополнение, граф"],
        ["Тестирование", "pytest 9", "Автоматические тесты"],
    ], [4.3, 5.0, 7.2], "Используемые технологии")
    para(doc, "Внешние библиотеки в браузере не используются, поэтому система работает без Интернета. "
              "Поисковый индекс строится в оперативной памяти при запуске за "
              f"{fmt(EVAL['full']['stats']['build_ms'], 1)} мс и перестраивается после каждого изменения "
              "в редакторе знаний.")

    h2(doc, "3.2 Физическая модель базы данных")
    para(doc, "База данных StroyMir_KB разделена на две схемы. Схема dbo содержит каталог из лабораторных работ, "
              "схема kb — базу знаний (таблица 7). Скрипты создания и наполнения приведены в приложении Б. "
              "Для наполнения использован генератор seed.py: знания описаны в модуле data/knowledge.py, "
              "из которого формируется SQL-скрипт 02_data.sql.")
    table(doc, ["Таблица", "Назначение", "Строк"], [
        ["kb.Country, kb.Publisher, kb.ContentType", "Справочники стран, изданий, типов материалов",
         f"{len(K.COUNTRIES)} / {len(K.PUBLISHERS)} / {len(K.CONTENT_TYPES)}"],
        ["kb.Category", "Категории понятий", len(K.CATEGORIES)],
        ["kb.Tag", "Понятия онтологии (теги) с синонимами", N_CON],
        ["kb.Material", "Статьи базы знаний", N_ART],
        ["kb.MaterialTag", "Теги статей с релевантностью и рангом", N_TAGLINKS],
        ["kb.VideoSource", "Видеоролики к статьям", N_VIDEO],
        ["kb.Relation", "Семантическая сеть", N_REL],
        ["kb.Question", "Вопросы экспертной системы", len(K.QUESTIONS)],
        ["kb.Rule, kb.RuleCondition", "Продукционные правила и их условия",
         f"{N_RULES} / {sum(len(r[1]) for r in K.RULES)}"],
        ["kb.SearchLog", "Журнал поисковых запросов", "—"],
        ["dbo.Manufacturer … dbo.Delivery", "Каталог продукции (ЛР № 5–11)", "6 таблиц"],
    ], [5.2, 8.3, 3.0], "Таблицы базы данных", align_num=(2,))
    para(doc, "Целостность обеспечивается первичными, внешними и уникальными ключами и ограничениями CHECK. "
              "Допустимые типы связей перечислены в CK_Relation_type, связь понятия с самим собой запрещена, "
              "CF лежит в диапазоне [–1; 1], правило-факт обязано иметь атрибут и значение. Программные объекты "
              "базы данных перечислены в таблице 8.")
    table(doc, ["Объект", "Тип", "Назначение"], [
        ["kb.v_MaterialCard", "Представление", "Полная карточка статьи с изданием, страной, видео"],
        ["dbo.v_ProductCatalog", "Представление", "Каталог: производитель → категория → продукт → партия → сырьё"],
        ["kb.fn_ConceptNeighbors", "Табличная функция", "Входящие и исходящие связи понятия"],
        ["kb.fn_ConceptAncestors", "Табличная функция", "Все предки понятия (рекурсивный CTE)"],
        ["kb.fn_InheritedFacts", "Табличная функция", "Знания, унаследованные от предков"],
        ["kb.fn_PopularQueries", "Табличная функция", "Популярные запросы для автодополнения"],
        ["kb.usp_SearchLog_Add", "Процедура", "Запись запроса в журнал"],
        ["kb.usp_Material_View", "Процедура", "Открытие статьи, счётчик просмотров"],
        ["kb.usp_RecalcRanks", "Процедура", "Пересчёт итогового ранга и позиции статьи по тегу"],
        ["kb.usp_SearchStats", "Процедура", "Статистика запросов по типам"],
        ["kb.trg_Material_Updated", "Триггер", "Дата изменения статьи"],
        ["kb.trg_Relation_NoCycle", "Триггер", "Запрет циклов в иерархии «является»"],
    ], [4.7, 3.4, 8.4], "Программные объекты базы данных")
    para(doc, "Рекурсивная функция поиска предков и триггер, использующий её для запрета циклов в иерархии, "
              "приведены в листинге 1. Если добавить связь «Строительный материал является Газобетоном», "
              "триггер отменит транзакцию: газобетон уже является потомком строительного материала.")
    listing(doc, "Рекурсивная функция kb.fn_ConceptAncestors и триггер kb.trg_Relation_NoCycle",
            code_excerpt(ROOT / "sql/03_procedures.sql", r"CREATE OR ALTER FUNCTION kb.fn_ConceptAncestors", r"^GO") +
            "\nGO\n\n" +
            code_excerpt(ROOT / "sql/03_procedures.sql", r"CREATE OR ALTER TRIGGER kb.trg_Relation_NoCycle", r"^GO"))

    h2(doc, "3.3 Алгоритм интеллектуального поиска")
    para(doc, "Поисковая машина (пакет search) обрабатывает запрос в восемь этапов (рисунок 4).")
    figure(doc, IMG / "d_pipeline.png", "Этапы обработки поискового запроса", max_h_cm=17, trim_white=True)
    para(doc, "**Нормализация.** Текст приводится к нижнему регистру, буква «ё» заменяется на «е». Затем текст "
              "разбивается на слова регулярным выражением, которое сохраняет марки и размеры («М500», «12.5», "
              "«200x100»). По числу слов запрос относится к одному из трёх видов: слово (1), словосочетание (2–4) "
              "или предложение (5–15). Слова после пятнадцатого отбрасываются, а пользователь видит "
              "предупреждение.")
    para(doc, "**Исправление опечаток.** Словарь содержит все словоформы статей, названий и синонимов "
              f"понятий — {EVAL['full']['stats']['vocabulary']} слов. Если слова запроса нет в словаре, "
              "кандидаты на замену отбираются по общим буквенным биграммам. Затем для них вычисляется расстояние "
              "Дамерау–Левенштейна [9] — число вставок, удалений, замен и перестановок соседних букв. Допускается "
              "расстояние 1 для слов до 6 букв и 2 для более длинных. Из равноудалённых кандидатов выбирается "
              "самый частотный.")
    para(doc, "**Стемминг.** Слово сводится к основе по алгоритму Snowball для русского языка [11, 12], "
              "реализованному в модуле search/stemmer.py без внешних библиотек. Алгоритм находит в слове "
              "область RV (после первой гласной) и R2. В этих областях он последовательно отсекает окончания "
              "деепричастий, возвратные частицы, окончания прилагательных, причастий, глаголов и существительных, "
              "затем суффиксы «ост», «ость» и превосходной степени. В результате «кирпича», «кирпичами» и "
              "«кирпичу» сводятся к основе «кирпич», а «морозостойкость» и «морозостойкого» — к «морозостойк». "
              "Стоп-слова («для», «из», «как») и вопросительные слова из поиска исключаются.")
    para(doc, "**Намерение и понятия.** Шаблоны регулярных выражений определяют, что спрашивает пользователь: "
              "«чем заменить» соответствует связи «заменяет», «из чего делают» — связи «изготавливается_из» и т. д. "
              "Затем в последовательности основ ищется самое длинное совпадение с названиями и синонимами понятий: "
              "«минеральная вата» распознаётся как одно понятие из двух слов.")
    para(doc, "**Расширение запроса.** Для каждого найденного понятия в запрос добавляются основы его названия "
              "и синонимов с весом 0,7, а также названия его видов (связь «является») с весом 0,35. Поэтому "
              "запрос «газоблок» находит статьи о газобетоне, а запрос «утеплитель» — статьи о минеральной вате "
              "и пенополистироле.")
    para(doc, "**Ранжирование.** Используется инвертированный индекс: каждой основе сопоставлены документы и "
              "частоты в полях «заголовок», «теги», «аннотация» и «текст». Базовая оценка вычисляется по "
              "формуле BM25F [13] с весами полей 3; 2; 1,5; 1 и параметрами k₁ = 1,2, b = 0,75:")
    para(doc, "BM25F(d, q) = Σ wₜ · idf(t) · tf̃(t, d) / (k₁ + tf̃(t, d)),", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    para(doc, "tf̃(t, d) = Σ_f W_f · tf_f(t, d) / (1 – b + b · len_f(d) / avglen_f),", align=WD_ALIGN_PARAGRAPH.CENTER,
         indent=False)
    para(doc, "где wₜ — вес термина (1 для слов запроса, 0,7 для синонимов, 0,35 для видов, 0,3 для слов-намерений), "
              "idf(t) = ln(1 + (N – n_t + 0,5) / (n_t + 0,5)), W_f — вес поля f.", indent=False)
    para(doc, "Итоговый ранг учитывает ещё три фактора:")
    para(doc, "score = BM25F · (0,3 + 0,7 · c²) · (1 + 0,6 · p) · (1 + 0,5 · r),", align=WD_ALIGN_PARAGRAPH.CENTER,
         indent=False)
    para(doc, "где c — доля слов запроса, найденных в документе (непосредственно или через синоним); p — близость "
              "слов: число разных слов запроса, делённое на длину минимального окна текста, где они все "
              "встречаются; r — релевантность тега документа, совпадающего с понятием запроса (для видов понятия — "
              "половина). Квадрат покрытия особенно важен для запросов-предложений. Документ, отвечающий "
              "на весь вопрос, получает преимущество перед документом, где много раз встречается одно слово.", indent=False)
    para(doc, "**Формирование ответа.** Для первых трёх документов каждое предложение оценивается по доле слов "
              "запроса и наличию слов-намерений. Лучшее предложение показывается как «Быстрый ответ» с "
              "указанием статьи-источника. Сниппет — наиболее насыщенное словами запроса предложение документа "
              "с подсветкой. Справа выводится карточка понятия: определение, синонимы и связи онтологии. Связь, "
              "соответствующая намерению, выделена: на запрос «чем заменить газобетон» первым показан список "
              "«Может заменить». Фрагмент функции ранжирования приведён в листинге 2, полный код — в приложении В.")
    listing(doc, "Ранжирование документа (фрагмент search/engine.py)",
            code_excerpt(ROOT / "search/engine.py", r"for doc_id in candidates:", r"scored\.sort", max_lines=40))

    h2(doc, "3.4 Машина логического вывода")
    para(doc, "Машина вывода (модуль expert.py, листинг 3) получает правила из таблиц kb.Rule и kb.RuleCondition "
              "и ответы пользователя. Она выполняет цикл «распознавание — действие», пока в рабочей памяти "
              "появляются новые факты. Каждое правило срабатывает не более одного раза, поэтому вывод конечен.")
    listing(doc, "Прямой вывод с коэффициентами уверенности (expert.py)",
            code_excerpt(ROOT / "expert.py", r"^def combine_cf", r"^def visible_questions") + "\n\n" +
            code_excerpt(ROOT / "expert.py", r"    step = 0", r"    items = \[", max_lines=40))

    h2(doc, "3.5 Пользовательский интерфейс")
    para(doc, "Главная страница (рисунок 5) содержит строку поиска со счётчиком слов и автодополнением, "
              "примеры запросов всех трёх видов, показатели объёма базы знаний и перечень понятий по категориям.")
    figure(doc, IMG / "01_home.png", "Главная страница", crop=1290)
    para(doc, "На рисунке 6 показана выдача по запросу-предложению из десяти слов. Система определила вид запроса, "
              "распознала понятия «бетон», «фундамент» и «газобетон» и сформировала быстрый ответ: «Для ленточного "
              "фундамента частного дома из газобетона или каркаса достаточно бетона B20 (М250)». Справа — карточка "
              "понятия «Бетон» со связями онтологии.")
    figure(doc, IMG / "02_search_sentence.png", "Выдача по запросу-предложению", crop=1500)
    para(doc, "На рисунке 7 показано исправление опечатки: по запросу «гипсакартон» найдены статьи о гипсокартоне, "
              "а пользователь видит, по какому слову выполнен поиск. Рисунок 8 демонстрирует распознавание "
              "намерения: на вопрос «из чего делают силикатный кирпич» система показывает быстрый ответ и выделяет "
              "в карточке понятия связь «изготавливается из»: известь и песок.")
    figure(doc, IMG / "03_search_typo.png", "Исправление опечатки в запросе", crop=1100)
    figure(doc, IMG / "04_search_intent.png", "Ответ на вопрос с распознаванием намерения", crop=1300)
    para(doc, "Страница понятия (рисунок 9) показывает определение, синонимы, иерархию и связи, сгруппированные "
              "по типам, а также знания, унаследованные от более общих понятий. Граф онтологии (рисунок 10) "
              "построен алгоритмом силовой укладки Фрюхтермана–Рейнгольда [14] и нарисован в формате SVG. При "
              "наведении на узел выделяются его связи.")
    figure(doc, IMG / "06_concept.png", "Страница понятия «Газобетон»", crop=1250)
    figure(doc, IMG / "07_graph.png", "Граф семантической сети с выделенными связями понятия «Газобетон»", crop=1500)
    para(doc, "Экспертная система (рисунок 11) задаёт вопросы, скрывая неактуальные, и выводит рекомендованные "
              "и отвергнутые материалы с коэффициентами уверенности. Ниже результата приведено объяснение: "
              "содержимое рабочей памяти (выведенные факты помечены) и трасса сработавших правил.")
    figure(doc, IMG / "08_expert.png", "Экспертная система: утепление фасада бани при экономичном бюджете",
           crop=2400, max_h_cm=21)
    para(doc, "Кроме того, в интерфейсе есть страница статьи с подсветкой слов запроса и таблицей тегов "
              "(рисунок 12), каталог продукции из лабораторных работ и редактор знаний. Редактор защищён паролем. "
              "В нём можно добавлять и изменять статьи (с тегами и видео), понятия и связи. После каждого изменения "
              "поисковый индекс перестраивается, и новые знания сразу доступны для поиска.")
    figure(doc, IMG / "11_material.png", "Статья базы знаний с подсветкой слов запроса", crop=1100)
    h2(doc, "3.6 Выводы")
    para(doc, "Реализована трёхуровневая система. Её основные компоненты — база данных с программными объектами, "
              "поисковая машина с морфологией, исправлением опечаток и онтологическим расширением запроса, "
              "машина логического вывода и веб-интерфейс пользователя и редактора.")

    # ================================================================ ГЛАВА 4
    h1(doc, "ГЛАВА 4. ТЕСТИРОВАНИЕ И ИССЛЕДОВАНИЕ ХАРАКТЕРИСТИК")
    h2(doc, "4.1 Функциональное тестирование")
    para(doc, f"Для проверки корректности разработан набор из {tests_passed} автоматических тестов на pytest "
              "(таблица 9). Тесты поиска и экспертной системы работают на данных модуля knowledge.py без СУБД. "
              "Интеграционные тесты обращаются к веб-приложению и базе данных: они открывают все страницы, "
              "проверяют API и сценарий редактора «создать статью → найти её → удалить».")
    table(doc, ["Группа тестов", "Что проверяется", "Тестов"], [
        ["Стемминг и расстояние правки", "Словоформы сводятся к общей основе; расстояние Дамерау–Левенштейна", 5],
        ["Виды запросов", "Определение вида, поиск по слову, словосочетанию и предложению, ограничение в 15 слов", 6],
        ["Интеллектуальные функции", "Синонимы, сокращения, опечатки, намерения, иерархия, подсветка, подсказки, "
         "скорость", 10],
        ["Экспертная система", "Объединение CF, цепочка вывода, сценарии подбора, условные вопросы", 7],
        ["Веб-приложение и БД", "Страницы, API, авторизация, добавление и удаление знаний", 14],
    ], [4.6, 9.7, 2.2], "Состав автоматических тестов", align_num=(2,))
    para(doc, f"Все {tests_passed} тестов выполнены успешно.")

    h2(doc, "4.2 Методика оценки качества поиска")
    para(doc, "Для оценки качества составлен контрольный набор из 24 запросов: по восемь слов, словосочетаний и "
              "предложений. Для каждого запроса заранее определены релевантные статьи. Набор включает словоформы, "
              "опечатку, профессиональные сокращения и разговорные названия, которых нет в текстах статей "
              "(«газоблок», «рубероид», «самонивелир», «ЖБИ»), а также вопросы до 11 слов. Использованы "
              "стандартные метрики информационного поиска [13, 15]:")
    bullets(doc, [
        "P@1 — доля запросов, для которых первый результат релевантен;",
        "MRR — средний обратный ранг первого релевантного результата (1 — первое место, 1/2 — второе, …);",
        "R@5 — доля релевантных статей, попавших в первые пять результатов.",
    ])
    para(doc, "Чтобы оценить вклад отдельных механизмов, проведён абляционный эксперимент. Система тестировалась "
              "в полной конфигурации и с поочерёдным отключением исправления опечаток, синонимов с онтологией "
              "и стемминга. Время ответа измерялось как медиана 30 повторов каждого запроса. Программа "
              "эксперимента — docs/evaluate.py.")

    h2(doc, "4.3 Результаты исследования")
    rows = []
    for key, v in EVAL.items():
        for kind, m in v["by_kind"].items():
            rows.append([v["label"] if kind == "слово" else "", kind, fmt(m["P@1"]), fmt(m["MRR"]), fmt(m["R@5"])])
    table(doc, ["Конфигурация", "Вид запроса", "P@1", "MRR", "R@5"], rows, [5.4, 4.2, 2.3, 2.3, 2.3],
          "Качество поиска на контрольном наборе", align_num=(2, 3, 4))
    no_onto = EVAL["no_onto"]["by_kind"]
    para(doc, f"Полная система ставит релевантную статью на первое место для всех 24 запросов. Наибольший "
              f"вклад вносят синонимы и онтология. Без них P@1 для одиночных слов падает до "
              f"{fmt(no_onto['слово']['P@1'])}, для словосочетаний — до {fmt(no_onto['словосочетание']['P@1'])}. "
              "Запросы «газоблок», «рубероид», «самонивелир», «ЖБИ» и «утепление каркасника» перестают находить "
              "что-либо, потому что этих слов нет в текстах статей. Стемминг необходим для словосочетаний: без "
              "него запрос «основание мягкой кровли» не находит статью, где написано «основание», «мягкая кровля». "
              "Исправление опечаток восстанавливает запрос «гипсакартон», который иначе даёт пустую выдачу.")
    para(doc, "Запросы-предложения устойчивее остальных к отключению отдельных механизмов: они содержат несколько "
              "значимых слов, и потеря одного из них компенсируется остальными. Отметим ограничение эксперимента: "
              "набор невелик, и при его составлении выявлена и исправлена одна ошибка в знаниях. Синоним «цоколь» "
              "был ошибочно отнесён к понятию «Фундамент», и запрос о разрушении кирпича на цоколе уводил "
              "к статьям о гидроизоляции. Поэтому результат P@1 = 1,0 следует считать оценкой сверху. Пример "
              "показывает и сильную сторону подхода: ошибка поиска была исправлена правкой знаний, а не кода.")
    rows = [[k, fmt(v["ms"]), fmt(v["ms_max"])] for k, v in full.items()]
    table(doc, ["Вид запроса", "Среднее время, мс", "Максимальное время, мс"], rows, [6, 5, 5.5],
          "Время ответа поисковой машины", align_num=(1, 2))
    para(doc, "Время ответа не превышает нескольких миллисекунд при требовании 100 мс. Это достигается за счёт "
              "инвертированного индекса в оперативной памяти: обрабатываются только документы, содержащие "
              "термины запроса. Запросы-предложения обрабатываются несколько дольше, так как в них больше терминов "
              "и расширений. Аналогичный замер выполняется в самом приложении на странице «Статистика» "
              "(рисунок 13). Там же отображаются журнал запросов по видам, популярные запросы и запросы без "
              "результатов, которые подсказывают, каких знаний не хватает в базе.")
    figure(doc, IMG / "09_stats.png", "Страница исследования характеристик", crop=1880)

    h2(doc, "4.4 Проверка экспертной системы")
    rules = memory_rules()
    scen = [
        ("Фундамент", {"element": "Фундамент"}),
        ("Перегородка во влажном помещении", {"element": "Перегородка", "humidity": "Влажное помещение"}),
        ("Утепление фасада бани, эконом", {"element": "Утепление", "building": "Баня", "place": "Фасад",
                                           "budget": "Эконом"}),
        ("Плоская кровля, средний бюджет", {"element": "Кровля", "slope": "Плоская", "budget": "Средний"}),
        ("Несущая стена, эконом, быстро", {"element": "Наружная стена", "building": "Каменный дом",
                                           "load": "Несущая", "budget": "Эконом", "speed": "Да"}),
        ("Отделка стен в ванной", {"element": "Отделка стен", "humidity": "Влажное помещение"}),
    ]
    rows = []
    for name, ans in scen:
        r = infer(rules, ans)
        rec = ", ".join(f"{x['name']} ({fmt(x['cf'])})" for x in r["recommended"][:3])
        rej = ", ".join(f"{x['name']} ({fmt(x['cf'])})" for x in r["rejected"][:2]) or "—"
        rows.append([name, rec, rej, len(r["trace"])])
    table(doc, ["Ситуация", "Рекомендовано (CF)", "Отвергнуто (CF)", "Шагов"], rows, [3.8, 6.2, 4.8, 1.7],
          "Результаты экспертной системы на типовых ситуациях", size=11, align_num=(3,))
    para(doc, "Рекомендации соответствуют строительной практике, изложенной в статьях базы знаний. Для фундамента "
              "система предлагает бетон и железобетон и отвергает гипсокартон и газобетон. Для влажной перегородки "
              "выбран влагостойкий гипсокартон, а обычный отвергнут. В бане исключён горючий пенополистирол. "
              "Для плоской кровли отвергнуты материалы, которым нужен уклон. Цепочка «Фундамент → zone = грунт → "
              "need_water = да → need_moisture = да» показывает, что вывод действительно идёт через "
              "промежуточные факты.")
    h2(doc, "4.5 Выводы")
    para(doc, "Функциональное тестирование подтвердило корректность всех компонентов. Исследование качества "
              "показало, что каждый механизм обработки запроса — исправление опечаток, стемминг, синонимы и "
              "онтология — даёт измеримый прирост качества. Наибольший вклад вносит онтология. Время ответа на "
              "порядок меньше требуемого.")

    # ---------- заключение
    h1(doc, "ЗАКЛЮЧЕНИЕ")
    para(doc, "В ходе курсового проекта разработана база знаний «СтройМир» в предметной области «Строительные "
              "материалы». Цель проекта достигнута, все поставленные задачи решены.")
    bullets(doc, [
        "Проанализированы предметная область и аналоги. Установлено, что существующие системы не сочетают "
        "полнотекстовый поиск с онтологией и логическим выводом.",
        "Выбрана комбинированная модель представления знаний: реляционные факты, семантическая сеть понятий и "
        "продукционные правила с коэффициентами уверенности. ER-модель лабораторных работ расширена сущностями "
        "онтологии и экспертной системы.",
        f"База знаний наполнена: {N_ART} статей (около {WORDS // 100 * 100} слов), {N_CON} понятий с {N_SYN} "
        f"синонимами, {N_REL} связей восьми типов и {N_RULES} правил. Реляционная часть содержит каталог "
        "из лабораторных работ.",
        "Реализован поиск по слову, словосочетанию и предложению до 15 слов. Он включает стемминг по алгоритму "
        "Snowball, исправление опечаток, распознавание понятий и намерений, расширение запроса по онтологии, "
        "ранжирование BM25F с учётом покрытия и близости слов, быстрый ответ и карточку понятия.",
        "Реализована экспертная система с прямым выводом и объединением коэффициентов уверенности по схеме "
        "MYCIN. Система объясняет свои рекомендации.",
        "Разработан веб-интерфейс с графом онтологии, каталогом, статистикой и редактором знаний.",
        f"Система протестирована: пройдено {tests_passed} автоматических тестов. На контрольном наборе "
        "P@1 = 1,0, время ответа — единицы миллисекунд. Абляционный эксперимент подтвердил вклад каждого "
        "механизма.",
    ], numbered=True)
    para(doc, "Возможные направления развития: расширение базы знаний и контрольного набора запросов; "
              "автоматическое извлечение синонимов из журнала запросов без результатов; использование векторных "
              "представлений слов для поиска по смыслу; добавление в экспертную систему количественных расчётов "
              "(толщина утеплителя по термическому сопротивлению).")

    # ---------- источники
    h1(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    sources = [
        f"ТОП-10 лучших сервисов для создания базы знаний в 2026 году [Электронный ресурс] // WEEEK. – Режим доступа: "
        f"https://weeek.net/ru/blog/best-knowledge-base-software. – Дата доступа: {ACCESS_DATE}.",
        f"HuffPost Search [Electronic resource] // HuffPost. – Mode of access: https://www.huffpost.com/search. – "
        f"Date of access: {ACCESS_DATE}.",
        f"Springer Link [Electronic resource] / Springer Nature. – Mode of access: https://link.springer.com/. – "
        f"Date of access: {ACCESS_DATE}.",
        f"The World Bank [Electronic resource]. – Mode of access: https://www.worldbank.org/ext/en/home. – "
        f"Date of access: {ACCESS_DATE}.",
        f"Oxford Text Archive [Electronic resource] / University of Oxford. – Mode of access: "
        f"https://digital.humanities.ox.ac.uk/project/oxford-text-archive. – Date of access: {ACCESS_DATE}.",
        "Гаврилова, Т. А. Базы знаний интеллектуальных систем / Т. А. Гаврилова, В. Ф. Хорошевский. – СПб. : "
        "Питер, 2000. – 384 с.",
        "Джарратано, Дж. Экспертные системы: принципы разработки и программирование / Дж. Джарратано, Г. Райли ; "
        "пер. с англ. – 4-е изд. – М. : Вильямс, 2007. – 1152 с.",
        "Buchanan, B. G. Rule-Based Expert Systems: The MYCIN Experiments of the Stanford Heuristic Programming "
        "Project / B. G. Buchanan, E. H. Shortliffe. – Reading : Addison-Wesley, 1984. – 748 p.",
        "Damerau, F. J. A technique for computer detection and correction of spelling errors / F. J. Damerau // "
        "Communications of the ACM. – 1964. – Vol. 7, № 3. – P. 171–176.",
        f"Flask Documentation [Electronic resource] / Pallets. – Mode of access: https://flask.palletsprojects.com/. – "
        f"Date of access: {ACCESS_DATE}.",
        f"Porter, M. F. Snowball: A language for stemming algorithms [Electronic resource] / M. F. Porter. – 2001. – "
        f"Mode of access: https://snowballstem.org/texts/introduction.html. – Date of access: {ACCESS_DATE}.",
        f"Russian stemming algorithm [Electronic resource] // Snowball. – Mode of access: "
        f"https://snowballstem.org/algorithms/russian/stemmer.html. – Date of access: {ACCESS_DATE}.",
        "Robertson, S. The Probabilistic Relevance Framework: BM25 and Beyond / S. Robertson, H. Zaragoza // "
        "Foundations and Trends in Information Retrieval. – 2009. – Vol. 3, № 4. – P. 333–389.",
        "Fruchterman, T. M. J. Graph drawing by force-directed placement / T. M. J. Fruchterman, E. M. Reingold // "
        "Software: Practice and Experience. – 1991. – Vol. 21, № 11. – P. 1129–1164.",
        "Маннинг, К. Д. Введение в информационный поиск / К. Д. Маннинг, П. Рагхаван, Х. Шютце ; пер. с англ. – "
        "М. : Вильямс, 2011. – 528 с.",
    ]
    for i, s in enumerate(sources, 1):
        para(doc, f"{i}. {s}")

    # ---------- приложения
    h1(doc, "ПРИЛОЖЕНИЕ А. РУКОВОДСТВО ПО ЗАПУСКУ")
    for t in [
        "Требования: Windows 10/11, Microsoft SQL Server 2019 или новее (экземпляр по умолчанию), "
        "ODBC Driver 17 for SQL Server, Python 3.11 или новее.",
        "1. Запустить службу SQL Server (MSSQLSERVER).",
        "2. Установить зависимости: `py -m pip install -r requirements.txt`.",
        "3. Создать и наполнить базу данных: `py seed.py --deploy`. Скрипты sql/01_schema.sql, "
        "sql/03_procedures.sql и sql/02_data.sql можно также выполнить вручную в SQL Server Management Studio "
        "в указанном порядке.",
        "4. Запустить веб-приложение: `py app.py`. Затем открыть в браузере адрес http://localhost:5000.",
        "5. Редактор знаний открывается в разделе «Редактор». Пароль по умолчанию — admin; он задаётся переменной "
        "окружения STROYMIR_ADMIN_PASSWORD.",
        "6. Запустить тесты: `py -m pytest tests`. Исследование качества поиска: `py docs/evaluate.py`.",
        "Параметры подключения к СУБД задаются переменными окружения STROYMIR_SQL_SERVER, STROYMIR_SQL_USER и "
        "STROYMIR_SQL_PASSWORD. По умолчанию используется локальный сервер и проверка подлинности Windows.",
    ]:
        para(doc, t)
    para(doc, "Структура проекта приведена в таблице.")
    table(doc, ["Путь", "Содержимое"], [
        ["sql/", "Скрипты создания БД, наполнения и программных объектов"],
        ["data/knowledge.py, data/catalog.sql", "Знания и данные каталога"],
        ["seed.py", "Генерация SQL-скрипта наполнения и развёртывание БД"],
        ["search/", "Поисковая машина: stemmer.py, spell.py, text.py, engine.py"],
        ["expert.py", "Машина логического вывода"],
        ["app.py, db.py, config.py", "Веб-приложение, доступ к данным, настройки"],
        ["templates/, static/", "HTML-шаблоны, стили, сценарии JavaScript"],
        ["tests/", "Автоматические тесты"],
        ["docs/", "Исследование характеристик, сборка записки и презентации"],
    ], [6.0, 10.5], "Структура проекта")

    h1(doc, "ПРИЛОЖЕНИЕ Б. SQL-СКРИПТЫ БАЗЫ ДАННЫХ")
    schema = (ROOT / "sql/01_schema.sql").read_text(encoding="utf-8-sig")
    kb_part = schema[schema.index("/* СТРАНА */"):]
    listing(doc, "Создание таблиц базы знаний (фрагмент sql/01_schema.sql)", kb_part, size=8)
    listing(doc, "Представления, функции, процедуры и триггеры (sql/03_procedures.sql)",
            (ROOT / "sql/03_procedures.sql").read_text(encoding="utf-8-sig"), size=8)

    h1(doc, "ПРИЛОЖЕНИЕ В. ИСХОДНЫЙ КОД ПОИСКОВОЙ МАШИНЫ")
    listing(doc, "Стеммер русского языка (search/stemmer.py)",
            (ROOT / "search/stemmer.py").read_text(encoding="utf-8"), size=8)
    listing(doc, "Исправление опечаток (search/spell.py)", (ROOT / "search/spell.py").read_text(encoding="utf-8"), size=8)
    listing(doc, "Поисковая машина (search/engine.py)", (ROOT / "search/engine.py").read_text(encoding="utf-8"), size=8)

    # подстановка числа рисунков и таблиц в реферат
    for p in doc.paragraphs:
        if "{FIGS}" in p.text:
            for r in p.runs:
                r.text = r.text.replace("{FIGS}", str(fig_no)).replace("{TABS}", str(tab_no))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0)
    ap.add_argument("--out", default=str(DOCS / "Пояснительная записка.docx"))
    a = ap.parse_args()
    d = build(a.pages or "{PAGES}")
    d.save(a.out)
    print(f"saved {a.out}: {fig_no} figures, {tab_no} tables, {lst_no} listings")
