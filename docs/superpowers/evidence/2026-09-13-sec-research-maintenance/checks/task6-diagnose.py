from tests.test_sec_research_maintenance import admin, api, preview


def test_observation_traceback(admin, monkeypatch):
    def expose(exc):
        raise exc

    monkeypatch.setattr(api(), "_code", expose)
    admin.captures.put(b"selected")
    with admin.store.connect() as conn:
        conn.execute("CREATE TABLE news(id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT)")
    assert preview(admin)["status"] == "ready"
