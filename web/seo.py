"""Render crawlable HTML and a sitemap using the same public knowledge data."""
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


def render_static_site(dist: Path, data: dict, site_url: str):
    site_url = site_url.rstrip('/') + '/'
    parsed = urlsplit(site_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Public site URL must be an absolute HTTP(S) URL without query or fragment')
    prefix = parsed.path
    esc = lambda value: html.escape(str(value), quote=True)
    concepts = {c['id']: c for c in data['concepts']}
    from docs.render_research import research_fragment

    def url(path=''):
        return site_url + path.strip('/') + ('/' if path.strip('/') else '')

    def link(path, text, css=''):
        return f'<a href="{esc(url(path))}" class="{esc(css)}">{esc(text)}</a>'

    def title(text, description=''):
        return f'<div class="page-head"><h1>{esc(text)}</h1><p>{esc(description)}</p></div>'

    def picture(d):
        g=d.get('guide')
        if not g: return ''
        image=g['image']
        return f'<img class="card-cover" src="./media/{esc(image["file"])}" alt="{esc(image["alt"])}" width="900" height="480" loading="lazy">'

    def rich_guide(d):
        g=d.get('guide')
        if not g: return ''
        result='<section class="reader-summary"><h2>Главное за минуту</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in g['takeaways'])+'</ul></section>'
        result+=f'<figure class="diagram"><img src="./media/{esc(g["diagram"]["file"])}" alt="{esc(g["diagram"]["alt"])}" width="900" height="455" loading="lazy"><figcaption>{esc(g["diagram"]["caption"])}</figcaption></figure>'
        result+='<h2>Проверить перед работой</h2><ol>'+''.join('<li>'+esc(x)+'</li>' for x in g['steps'])+'</ol><h2>Частые ошибки</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in g['mistakes'])+'</ul>'
        if g['videos']:
            result+='<h2>Видео по теме</h2><ul>'+''.join(f'<li><a href="{esc(v["url"])}" target="_blank" rel="noopener">{esc(v["title"])}</a> · {esc(v["author"])}</li>' for v in g['videos'])+'</ul>'
        image=g['image']
        result+=f'<details class="source-list"><summary>Источники и изображения</summary><p>{esc(image["alt"])} · {esc(image["author"])} · <a href="{esc(image["source"])}">Источник изображения</a> · <a href="{esc(image["license_url"])}">{esc(image["license"])}</a></p><ul>'+''.join(f'<li><a href="{esc(u)}">{esc(u)}</a></li>' for u in g['sources'])+'</ul></details>'
        return result

    def article_card(d):
        return f'<article class="article-card">{picture(d)}<small>{esc(d["type"])}</small><h3>{link("material/"+str(d["id"]),d["title"])}</h3><p>{esc(d["summary"])}</p></article>'

    def concept_chips(cs):
        return '<div class="examples">'+''.join(link('concept/'+str(c['id']),c['name'],'chip tag') for c in cs)+'</div>'

    pages = {}
    home = '''<section class="hero"><p class="eyebrow">СтройМир · база знаний Дусова А.Э.</p>
        <h1>Разберитесь в материалах.<br><span>Выберите подходящий.</span></h1>
        <p class="intro">ctroimir — интеллектуальная база знаний по строительным материалам.
        Состав, свойства, применение и объяснимый подбор материалов для строительства.</p>'''
    home += f'<div class="quick-links">{link("search","Найти материал","btn")}{link("expert","Подобрать материал","btn secondary")}</div></section>'
    home += '<div class="tiles">'+''.join(f'<div class="tile"><div class="n">{n}</div><div class="l">{label}</div></div>' for n,label in [(len(data['documents']),'статей'),(len(concepts),'понятий'),(len(data['relations']),'связей'),(len(data['rules']),'правил')])+'</div>'
    home += '<h2>Выберите задачу</h2><div class="examples">'+''.join(link('guides',c['name'],'chip') for c in data.get('collections',[]))+'</div>'
    home += '<h2>Статьи о строительных материалах</h2><div class="article-list">'+''.join(article_card(d) for d in data['documents'])+'</div>'
    home += '<h2>Понятия и определения</h2>'+concept_chips(data['concepts'])
    pages[''] = ('ctroimir — СтройМир Дусова, база знаний по строительным материалам',
                 'ctroimir — база знаний Дусова А.Э.: строительные материалы, практические статьи, поиск, онтология и экспертный подбор с объяснениями.', home,
                 {'@context':'https://schema.org','@type':'WebSite','name':'ctroimir','alternateName':'СтройМир Дусова','url':site_url,'inLanguage':'ru'})
    for d in data['documents']:
        path = 'material/'+str(d['id'])
        content = f'<div class="page-actions">{link("","Главная","btn secondary")}{link("concepts","Понятия базы знаний","btn secondary")}</div><article class="material"><div class="meta">{esc(d["type"])} · {esc(d["publisher"])}</div><h1>{esc(d["title"])}</h1><p class="lead">{esc(d["summary"])}</p>'
        if d["guide"]["image"]["file"] != d["guide"]["diagram"]["file"]:
            content += picture(d)
        content += ''.join('<p>'+esc(p)+'</p>' for p in d['body'].splitlines() if p.strip())
        content += rich_guide(d)
        content += '</article><h2>Понятия статьи</h2>'+concept_chips([concepts[t['id']] for t in d['tags']])
        related = [other for other in data['documents'] if other['id'] != d['id'] and {t['id'] for t in d['tags']} & {t['id'] for t in other['tags']}][:4]
        if related:
            content += '<h2>Читайте также</h2><div class="article-list">'+''.join(article_card(x) for x in related)+'</div>'
        pages[path] = (d['title']+' — ctroimir',d['summary'],content,
                       {'@context':'https://schema.org','@type':'Article','headline':d['title'],'description':d['summary'],'datePublished':d['date'],
                        'author':{'@type':'Person','name':'Дусов А.Э.'},'inLanguage':'ru','mainEntityOfPage':url(path)})
    for c in concepts.values():
        content = title(c['name'],c['category'])+f'<p class="definition">{esc(c["description"])}</p>'
        if c['synonyms']:
            content += '<p>Другие названия: '+esc(', '.join(c['synonyms']))+'</p>'
        facts=[p for p in data.get('properties',[]) if p['concept']==c['name'] or p['label']==c['name']]
        if facts:
            content+='<h2>Числовые атрибуты</h2><p>Учебный каталог; условия измерения и паспорт не указаны. Это не проектные характеристики.</p><div class="table-wrap"><table class="grid"><tr><th>Изделие</th><th>Атрибут</th><th>Значение</th><th>Единица</th><th>Источник</th></tr>'
            for p in facts:
                content+=f'<tr><td>{esc(p["product"])}</td><td>{esc(p["label"])}</td><td>{p["value"]}</td><td>{esc(p["unit"])}</td><td><a href="{esc(p["source_url"])}">{esc(p["source_kind"])}</a></td></tr>'
            content+='</table></div>'
        content += '<h2>Связи понятия</h2><ul>'
        out_replacements={r['to'] for r in data['relations'] if r['from']==c['id'] and r['type']=='заменяет'}
        in_replacements={r['from'] for r in data['relations'] if r['to']==c['id'] and r['type']=='заменяет'}
        mutual=out_replacements & in_replacements
        for r in data['relations']:
            if r['from'] == c['id']:
                target, label = r['to'], data['labels'][r['type']][0]
            elif r['to'] == c['id']:
                target, label = r['from'], data['labels'][r['type']][1]
            else:
                continue
            if r['type']=='заменяет' and target in mutual:
                if r['to']==c['id']:continue
                label='Взаимная замена (зависит от условий)'
            content += '<li>'+esc(label)+': '+link('concept/'+str(target),concepts[target]['name'])+'</li>'
        content += '</ul>'
        docs = [d for d in data['documents'] if any(t['id'] == c['id'] for t in d['tags'])]
        if docs:
            content += '<h2>Статьи по теме</h2><div class="article-list">'+''.join(article_card(d) for d in docs)+'</div>'
        pages['concept/'+str(c['id'])] = (c['name']+' — определение и применение | ctroimir',c['description'],content,
                                        {'@context':'https://schema.org','@type':'DefinedTerm','name':c['name'],'description':c['description'],'url':url('concept/'+str(c['id']))})
    content = title('Понятия базы знаний','Строительные материалы, свойства, нормативы и технологии.')
    for cat in data['categories']:
        content += '<h2>'+esc(cat['name'])+'</h2>'+concept_chips([c for c in concepts.values() if c['category_id'] == cat['id']])
    pages['concepts'] = ('Понятия строительных материалов — ctroimir','Понятия с определениями, синонимами и семантическими связями.',content,None)
    content = title('О проекте ctroimir')+'<div class="prose"><p>Курсовой проект Дусова А.Э. «Проектирование базы знаний по строительным материалам».</p><p>Сайт ctroimir объединяет статьи, онтологию и экспертную систему с объяснением рекомендаций. Поиск учитывает словоформы, синонимы и опечатки.</p><h2>Разделы проекта</h2><ul>'
    for path,label in [('concepts','Понятия'),('expert','Подбор материалов'),('graph','Граф онтологии'),('catalog','Каталог'),('rules','Экспертные правила')]:
        content += '<li>'+link(path,label)+'</li>'
    content += '</ul><p>Интерактивные поиск и подбор работают в браузере. Статьи и определения также доступны без JavaScript.</p></div>'
    pages['about'] = ('О проекте СтройМир Дусова — ctroimir','База знаний по строительным материалам: курсовой проект Дусова А.Э., поиск, онтология и экспертный вывод.',content,None)
    content = title('Каталог строительных материалов','Учебные данные о материалах, производителях и характеристиках. Цены в BYN не являются предложением продажи.')+'<div class="article-list">'
    for p in data['products']:
        content += '<article class="article-card"><h2>'+esc(p['name'])+'</h2><p>'+esc(p['manufacturer'])+'</p><p>'+esc(p['category'])+'</p></article>'
    content += '</div>'
    pages['catalog'] = ('Каталог строительных материалов — ctroimir','Материалы, производители и характеристики из учебного каталога проекта.',content,None)
    content = title('База экспертных правил','Полные условия ЕСЛИ, заключения ТО и происхождение авторских весов CF.')
    content+='<p class="model-note">CF назначены автором учебной модели. Они не являются вероятностями или нормативными коэффициентами. Технические источники не подтверждают численные веса.</p><div class="table-wrap"><table class="grid"><tr><th>Код</th><th>ЕСЛИ</th><th>ТО</th><th>CF</th><th>Объяснение и источник</th></tr>'
    for rule in data['rules']:
        conclusion=rule['then_attribute']+' = '+rule['then_value'] if rule['then_kind']=='fact' else rule['tag_name']
        conditions=' И '.join(a+' = '+v for a,v in rule['conditions'])
        provenance=rule['provenance']
        notes=f'<details><summary>{esc(provenance["kind"])} · источник и вес</summary><p>{esc(provenance["cf_basis"])}</p><a href="{esc(provenance["source_url"])}">{esc(provenance["source_label"])}</a>'
        for ref in provenance['references']:
            notes+=f'<p><a href="{esc(ref["url"])}">{esc(ref["title"])}</a><br>{esc(ref["scope"])}</p>'
        content+=f'<tr><td>{esc(rule["code"])}</td><td>{esc(conditions)}</td><td>{esc(conclusion)}</td><td>{rule["cf"]}</td><td>{esc(rule["explanation"])}{notes}</details></td></tr>'
    content+='</table></div>'
    pages['rules'] = ('Экспертные правила — ctroimir','Условия, выводы, авторские веса и технический контекст правил.',content,None)
    pages['expert'] = ('Подбор строительных материалов — ctroimir','Экспертный подбор материалов для стен, фундамента, кровли, утепления и отделки.',title('Подбор строительных материалов')+'<p>Включите JavaScript, чтобы ответить на вопросы и получить рекомендации с объяснениями.</p>'+link('rules','Посмотреть правила подбора'),None)
    pages['graph'] = ('Онтология строительных материалов — ctroimir','Семантическая сеть: Понятия и семантические связи строительных материалов, свойств и технологий.',title('Онтология строительных материалов')+concept_chips(data['concepts']),None)
    pages['search'] = ('Поиск по строительным материалам — ctroimir','Поиск по базе знаний с учётом словоформ, синонимов и опечаток.',title('Поиск по базе знаний')+'<p>Включите JavaScript для интеллектуального поиска.</p>',None)
    pages['stats'] = ('Исследование базы знаний — ctroimir','Измерение скорости поиска на устройстве посетителя.',title('Исследование базы знаний')+research_fragment(data.get('research'))+f'<p><a href="{esc(site_url)}research-results.json" download>Скачать исходные результаты JSON</a></p>',None)

    content=title('Практические инструкции','Стены, утепление, кровля, ванная и участок. Выберите статью под свою задачу.')
    for collection in data.get('collections',[]):
        content+='<h2>'+esc(collection['name'])+'</h2><div class="article-list">'+''.join(article_card(d) for d in data['documents'] if d['id'] in collection['articles'])+'</div>'
    pages['guides']=('Практические инструкции — ctroimir','Пошаговые материалы, схемы, частые ошибки и видео по строительству и ремонту.',content,None)
    seen=set(); content=title('Видеотека','Уроки производителей со ссылками на текстовые инструкции.')+'<ul>'
    for d in data['documents']:
        for v in d.get('guide',{}).get('videos',[]):
            if v['url'] in seen: continue
            seen.add(v['url'])
            content+=f'<li><a href="{esc(v["url"])}">{esc(v["title"])}</a> · {esc(v["author"])} · '+link('material/'+str(d['id']),'Статья по теме')+'</li>'
    pages['videos']=('Видеотека — ctroimir','Наглядные уроки КНАУФ, ТЕХНОНИКОЛЬ и Ceresit.',content+'</ul>',None)
    pages['library']=('Мои материалы — ctroimir','Ваши избранные и недавно прочитанные материалы.',title('Мои материалы')+'<p>Для избранного и истории чтения включите JavaScript. Записи хранятся только в вашем браузере.</p>',None)

    template = (dist/'index.html').read_text(encoding='utf-8')
    for path,(page_title,description,content,structured) in pages.items():
        canonical = url(path)
        page = re.sub(r'<title>.*?</title>', '<title>'+esc(page_title)+'</title>', template, flags=re.S)
        page = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="'+esc(description)+'">',page)
        robots = 'noindex,follow' if path in {'search','stats','library'} else 'index,follow,max-image-preview:large'
        meta = f'<meta name="site-root" content="{esc(site_url)}">\n<link rel="canonical" href="{esc(canonical)}">\n<meta name="robots" content="{robots}">\n<meta property="og:title" content="{esc(page_title)}">\n<meta property="og:description" content="{esc(description)}">\n<meta property="og:url" content="{esc(canonical)}">\n<meta property="og:site_name" content="ctroimir">\n<meta property="og:type" content="{"article" if path.startswith("material/") else "website"}">'
        if structured:
            meta += '<script type="application/ld+json">'+json.dumps(structured,ensure_ascii=False).replace('<','\\u003c')+'</script>'
        page = page.replace('</head>',meta+'\n</head>')
        page = re.sub(r'(<main\b[^>]*>).*?(</main>)',lambda m:m.group(1)+content+m.group(2),page,flags=re.S).replace('aria-busy="true"','aria-busy="false"')
        page = re.sub(r'href="#/([^"]*)"',lambda m:'href="'+esc(url(m.group(1)))+'"',page)
        depth = len(path.split('/')) if path else 0
        assets = '../'*depth if depth else './'
        page = page.replace('href="./','href="'+assets).replace('src="./','src="'+assets)
        target = dist/path/'index.html' if path else dist/'index.html'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(page,encoding='utf-8')
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('',namespace)
    root = ET.Element('{'+namespace+'}urlset')
    for path in pages:
        if path not in {'search','stats','library'}:
            item = ET.SubElement(root,'{'+namespace+'}url')
            ET.SubElement(item,'{'+namespace+'}loc').text = url(path)
    ET.ElementTree(root).write(dist/'sitemap.xml',encoding='utf-8',xml_declaration=True)
    # On a project site robots.txt is at the project path; the root account's
    # robots policy also applies. Sitemap submission uses the absolute URL.
    (dist/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+site_url+'sitemap.xml\n',encoding='utf-8')
    print(f'SEO: {len(pages)} HTML pages; {len(pages)-3} sitemap URLs; canonical base {site_url}')
    return len(pages)
