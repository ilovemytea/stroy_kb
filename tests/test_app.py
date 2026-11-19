"""Интеграционные тесты веб-приложения. Требуют запущенный SQL Server с базой StroyMir_KB;
без неё пропускаются."""
import pytest

try:
    import db
    db.query("SELECT 1 AS ok")
    DB_OK = True
except Exception:
    DB_OK = False

pytestmark = pytest.mark.skipif(not DB_OK, reason="SQL Server / StroyMir_KB недоступны")


@pytest.fixture(scope="module")
def client():
    import app as webapp
    webapp.app.config["TESTING"] = True
    with webapp.app.test_client() as c:
        yield c


@pytest.mark.parametrize("url", ["/", "/concepts", "/graph", "/expert", "/expert/rules", "/catalog",
                                 "/stats", "/concept/1", "/material/1", "/api/graph"])
def test_pages_open(client, url):
    assert client.get(url).status_code == 200


def test_search_page(client):
    r = client.get("/search", query_string={"q": "из чего делают силикатный кирпич"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Быстрый ответ" in html and "Известь" in html


def test_api_search(client):
    data = client.get("/api/search", query_string={"q": "минвата"}).get_json()
    assert data["kind"] == "слово"
    assert data["concepts"] == ["Минеральная вата"]
    assert data["results"]


def test_admin_requires_login(client):
    assert client.get("/admin").status_code == 302


def test_admin_create_search_delete(client):
    import config
    client.post("/admin/login", data={"password": config.ADMIN_PASSWORD})
    pubs, types = db.publishers(), db.content_types()
    title = "Тестовая статья про фибробетон"
    r = client.post("/admin/material/new", data={
        "title": title, "summary": "Проверка добавления знаний",
        "body": "Фибробетон — бетон, армированный дисперсными волокнами (фиброй). "
                "Фибра повышает трещиностойкость и ударную прочность.",
        "id_izdanie": pubs[0]["id_izdanie"], "id_type": types[0]["id_type"],
        "tags": "Бетон | 0.8\nАрмирование | 0.6",
    })
    assert r.status_code == 302
    mid = int(r.headers["Location"].rstrip("/").split("/")[-1])
    try:
        found = client.get("/api/search", query_string={"q": "фибробетон"}).get_json()
        assert found["results"][0]["title"] == title
    finally:
        client.post(f"/admin/material/{mid}", data={"delete": "1"})
    gone = client.get("/api/search", query_string={"q": "фибробетон"}).get_json()
    assert all(x["title"] != title for x in gone["results"])
    db.execute("DELETE FROM kb.SearchLog WHERE query_text = N'фибробетон'")


def test_practical_guide_pages(client):
    response=client.get('/guides')
    text=response.get_data(as_text=True)
    assert response.status_code==200
    assert 'Гидроизоляция ванной' in text and 'data-local-card' in text
    article=client.get('/material/10')
    text=article.get_data(as_text=True)
    assert article.status_code==200
    assert 'Посмотрите на схему' in text and 'data-local-save' in text
    assert 'data-local-video' in text and '/static/media/drywall.jpg' in text
