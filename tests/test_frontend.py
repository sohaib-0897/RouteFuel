"""Frontend shell integration must not affect the standalone API."""

from django.test import Client


def test_frontend_serves_built_shell(tmp_path, settings):
    settings.FRONTEND_DIST = tmp_path
    (tmp_path / "index.html").write_text("<html>RouteFuel</html>", encoding="utf-8")
    response = Client().get("/")
    assert response.status_code == 200
    assert b"RouteFuel" in b"".join(response.streaming_content)
    assert response["Cache-Control"] == "no-cache"


def test_missing_frontend_does_not_break_api_docs(tmp_path, settings):
    settings.FRONTEND_DIST = tmp_path
    client = Client()
    assert client.get("/").status_code == 503
    assert client.get("/api/docs/").status_code == 200
