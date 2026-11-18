"""Notify IndexNow about published URLs. HTTP 200/202 is not an indexing guarantee.

Run after deploying and verifying the public site. The ownership proof is
intentionally hosted as a public text file, as required by the protocol.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def submit():
    config = json.loads((ROOT/'indexnow.json').read_text(encoding='utf-8'))
    urls = [e.text for e in ET.parse(ROOT/'dist/sitemap.xml').findall('.//{*}loc')]
    if not urls or len(urls) > 10000:
        raise ValueError('Expected 1–10000 sitemap URLs')
    base = urls[0]
    key_file = config['key_file']
    key = (ROOT/'src'/key_file).read_text(encoding='utf-8').strip()
    key_url = base+key_file
    with urlopen(key_url, timeout=30) as response:
        if response.status != 200 or response.read().decode('utf-8').strip() != key:
            raise RuntimeError('Ownership proof is not published yet')
    if any(not u.startswith(base) for u in urls):
        raise ValueError('Sitemap contains a URL outside the verified project path')
    payload = {'host':urlsplit(base).hostname,'key':key,'keyLocation':key_url,'urlList':urls}
    request = Request(config['endpoint'],data=json.dumps(payload).encode('utf-8'),
                      headers={'Content-Type':'application/json; charset=utf-8','User-Agent':'dusovstroimir-site-publisher'},method='POST')
    with urlopen(request,timeout=30) as response:
        if response.status not in {200,202}:
            raise RuntimeError('IndexNow did not accept the submission')
        print(f'IndexNow accepted {len(urls)} URLs (HTTP {response.status}). Crawling and indexing remain the search engine’s decision.')


if __name__ == '__main__':
    submit()
