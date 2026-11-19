"""Local startup persists unique secrets without weakening explicit WSGI setup."""
import json
import pytest
from local_setup import configure_local, KEYS


def test_local_settings_persist(tmp_path):
    path=tmp_path/'.env.local.json'
    first={}
    assert configure_local(path,first)==path
    second={}
    configure_local(path,second)
    assert first==second and all(len(first[k])>=32 for k in KEYS)
    assert json.loads(path.read_text(encoding='utf-8'))==first
    other={}
    configure_local(tmp_path/'other.json',other)
    assert all(first[k]!=other[k] for k in KEYS)


def test_explicit_settings_override_local(tmp_path):
    path=tmp_path/'.env.local.json'
    configure_local(path,{})
    original=path.read_bytes()
    env={'STROYMIR_ADMIN_PASSWORD':'explicit-editor-password'}
    configure_local(path,env)
    assert env['STROYMIR_ADMIN_PASSWORD']=='explicit-editor-password'
    assert env['STROYMIR_SECRET_KEY']
    assert path.read_bytes()==original


def test_fully_configured_launch_creates_no_file(tmp_path):
    path=tmp_path/'.env.local.json'
    env={k:'explicit-value' for k in KEYS}
    assert configure_local(path,env) is None
    assert not path.exists()


@pytest.mark.parametrize('content',['not json','{}','{"STROYMIR_ADMIN_PASSWORD": []}'])
def test_invalid_settings_are_not_overwritten(tmp_path,content):
    path=tmp_path/'.env.local.json'
    path.write_text(content,encoding='utf-8')
    with pytest.raises(RuntimeError): configure_local(path,{})
    assert path.read_text(encoding='utf-8')==content
