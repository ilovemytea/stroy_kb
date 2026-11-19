"""Content integrity: prevent broken article media and dangling ontology links."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from data import knowledge as K
from data.enrichment import guide_for
from search.engine import RELATION_LABELS

def test_knowledge_references():
    names=[c[0] for c in K.CONCEPTS]
    assert len(names)==len(set(names))
    for src,rel,dst in K.RELATIONS:
        assert src in names and dst in names and rel in RELATION_LABELS
    for article in K.ARTICLES:
        assert all(tag in names for tag,_ in article[5])

def test_article_media_and_sources():
    root=Path(__file__).resolve().parent.parent/'static/media'
    videos=set()
    for article in K.ARTICLES:
        g=guide_for(article)
        assert g['takeaways'] and g['steps'] and g['mistakes']
        image=g['image']
        assert image['author'] and image['license'] and image['source'].startswith(('http://','https://'))
        for file in (image['file'],g['diagram']['file']):
            path=root/file
            assert path.is_file(), (article[0],file)
            if path.suffix=='.svg': ET.parse(path)
            else: assert path.read_bytes().startswith(bytes.fromhex('ffd8'))
        for video in g['videos']:
            assert '/results?' not in video['url']
            assert video['title'] and video['author'] and video['source']
            if 'youtube_id' in video: assert re.fullmatch(r'[\w-]{11}',video['youtube_id'])
            videos.add(video['url'])
    assert len(videos)>=9
