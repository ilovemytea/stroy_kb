"""Regression checks for the optional model and research methodology."""
import hashlib
import json
from pathlib import Path
import sys
import os
import secrets
import subprocess
from collections import Counter
import pytest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'docs'))
from data import knowledge as K
from data.review_model import CATALOG_ISSUES,DEFINITIONS,property_records,rule_note
from evaluate import evaluation_mode
from search import text
from web.build_public import catalog


def test_disabled_stemming_covers_queries_and_restores_on_error():
    normal=text.stem('кирпичами')
    with pytest.raises(RuntimeError):
        with evaluation_mode('no_stem'):
            assert text.stem('кирпичами')=='кирпичами'
            raise RuntimeError('Interrupted measurement')
    assert text.stem('кирпичами')==normal
    assert normal!='кирпичами'


def test_density_is_connected_without_duplicate_relations():
    assert len(K.RELATIONS)==len(set(K.RELATIONS))
    degree=Counter(n for a,_,b in K.RELATIONS for n in (a,b))
    assert degree['Плотность']>0
    assert not [c[0] for c in K.CONCEPTS if degree[c[0]]==0]


def test_typed_properties_preserve_units_and_exclude_known_conflict():
    facts=property_records(catalog(ROOT))
    assert facts
    assert not any(p['product_id'] in CATALOG_ISSUES for p in facts)
    assert len({(p['product_id'],p['attribute']) for p in facts})==len(facts)
    for p in facts:
        assert p['unit']==DEFINITIONS[p['attribute']][1]
        assert p['value']>0 and p['conditions'] and p['source_url']


def test_every_rule_discloses_author_assigned_weight():
    for rule in K.RULES:
        note=rule_note(rule)
        assert note['kind'] and note['cf_basis'] and note['source_url']
        assert 'не является вероятностью' in note['cf_basis']
    r21=next(r for r in K.RULES if r[0]=='R21')
    r22=next(r for r in K.RULES if r[0]=='R22')
    assert r21[1]!=r22[1]


def test_research_snapshot_matches_actual_model_and_contains_raw_samples():
    r=json.loads((ROOT/'docs/research-results.json').read_text(encoding='utf-8'))
    fingerprint=hashlib.sha256(json.dumps([K.CONCEPTS,K.RELATIONS,K.ARTICLES,K.RULES],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    assert r['dataset_sha256']==fingerprint
    assert r['counts']['concepts']==len(K.CONCEPTS)
    for stage in r['scaling']['stages']:
        assert len(stage['build']['samples_ms'])==10
        assert all(len(q['samples_ms'])==30 for q in stage['search'])
    assert r['expert']['passed']==r['expert']['total']


def test_static_rule_html_includes_conditions_conclusion_weight_and_provenance():
    page=(ROOT/'web/dist/rules/index.html').read_text(encoding='utf-8')
    for word in ['ЕСЛИ','ТО','CF','Эконом','Газобетон','Авторская эвристика','не являются вероятностями']:
        assert word in page
    assert 'Самый дешёвый утеплитель' not in page


def test_experiment_rejects_working_database_before_serving_or_syncing():
    env=os.environ.copy()
    env['STROYMIR_SQL_DATABASE']='StroyMir_KB'
    env['STROYMIR_ADMIN_PASSWORD']=secrets.token_hex(20)
    env['STROYMIR_SECRET_KEY']=secrets.token_hex(32)
    for command in ['import app','from sync_knowledge import sync; sync()']:
        result=subprocess.run([sys.executable,'-c',command],cwd=ROOT,env=env,capture_output=True,text=True,errors='replace')
        assert result.returncode!=0
        assert '_Review_' in result.stderr


def test_review_sql_scripts_never_target_working_database():
    import re
    for name in ['01_schema.sql','02_data.sql','03_procedures.sql']:
        source=(ROOT/'sql'/name).read_text(encoding='utf-8-sig')
        assert 'StroyMir_KB_Review_20261121' in source
        assert not re.search(r'\bStroyMir_KB\b',source)
