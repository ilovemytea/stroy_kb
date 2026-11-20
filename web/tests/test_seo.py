"""Check the published HTML itself, without relying on JavaScript rendering."""
import html
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
BASE = 'http://dusovstroimir.mooo.com/'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.canonical = None
        self.robots = ''
        self.description = ''
        self.h1 = 0
        self.links = []
        self.assets = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h1':
            self.h1 += 1
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a['href']
        if tag == 'meta':
            if a.get('name') == 'robots': self.robots = a.get('content', '')
            if a.get('name') == 'description': self.description = a.get('content', '')
        if tag == 'a' and 'href' in a: self.links.append(a['href'])
        if tag == 'img':
            assert a.get('alt')
            self.assets.append(a['src'])
        if tag == 'script' and 'src' in a: self.assets.append(a['src'])
        if tag == 'link' and a.get('rel') in {'stylesheet', 'icon', 'manifest'}: self.assets.append(a['href'])


def run():
    sitemap = ET.parse(DIST/'sitemap.xml')
    urls = [e.text for e in sitemap.findall('.//{*}loc')]
    data = json.loads((DIST/'knowledge.json').read_text(encoding='utf-8'))
    assert len(urls) == len(data['documents']) + len(data['concepts']) + 9
    assert len(urls) == len(set(urls))
    pages = list(DIST.rglob('index.html'))
    assert len(pages) == len(urls) + 3
    for file in pages:
        text = file.read_text(encoding='utf-8')
        page = Page(text)
        relative = file.parent.relative_to(DIST).as_posix()
        path = '' if relative == '.' else relative+'/'
        assert page.canonical == BASE+path, (file, page.canonical)
        assert page.h1 == 1 and page.description
        assert page.robots.startswith('noindex' if relative in {'search', 'stats', 'library'} else 'index')
        for asset in page.assets:
            assert (file.parent/urlsplit(asset).path).resolve().is_file(), (file, asset)
        for target in page.links:
            if target.startswith(BASE):
                route = urlsplit(target).path.removeprefix(urlsplit(BASE).path)
                assert (DIST/route/'index.html').is_file() or (DIST/route).is_file(), (file, target)
        for ld in __import__('re').findall(r'<script type="application/ld\+json">(.*?)</script>', text):
            json.loads(ld)
    data = json.loads((DIST/'knowledge.json').read_text(encoding='utf-8'))
    for d in data['documents']:
        text = (DIST/'material'/str(d['id'])/'index.html').read_text(encoding='utf-8')
        assert html.escape(d['title']) in text
        for paragraph in d['body'].splitlines():
            if paragraph.strip(): assert html.escape(paragraph) in text
    assert 'Disallow: /' not in (DIST/'robots.txt').read_text(encoding='utf-8')
    print(f'PASS: {len(pages)} HTML pages, {len(urls)} sitemap URLs; complete articles, media, links and metadata.')


if __name__ == '__main__':
    run()
