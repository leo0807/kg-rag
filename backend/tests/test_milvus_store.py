from src.services.storage import milvus_store


def test_ensure_milvus_connected_reconnects_when_alias_is_only_configured(monkeypatch):
    events: list[tuple[str, object]] = []
    state = {"has_connection": False}

    monkeypatch.setattr(
        milvus_store.connections,
        "has_connection",
        lambda alias: state["has_connection"],
    )

    def fake_list_collections():
        events.append(("list", state["has_connection"]))
        if not state["has_connection"]:
            raise RuntimeError("not connected")
        return []

    def fake_disconnect(alias):
        events.append(("disconnect", alias))

    def fake_connect(host, port):
        events.append(("connect", (host, port)))
        state["has_connection"] = True

    monkeypatch.setattr(milvus_store.utility, "list_collections", fake_list_collections)
    monkeypatch.setattr(milvus_store.connections, "disconnect", fake_disconnect)
    monkeypatch.setattr(milvus_store, "connect_milvus", fake_connect)

    milvus_store.ensure_milvus_connected()

    assert ("disconnect", "default") in events
    assert ("connect", (milvus_store.settings.MILVUS_HOST, str(milvus_store.settings.MILVUS_PORT))) in events
    assert events[-1] == ("list", True)


def test_ensure_milvus_connected_skips_reconnect_when_alive(monkeypatch):
    monkeypatch.setattr(milvus_store.connections, "has_connection", lambda alias: True)
    monkeypatch.setattr(milvus_store.utility, "list_collections", lambda: [])

    def fail_disconnect(alias):
        raise AssertionError("should not disconnect")

    def fail_connect(host, port):
        raise AssertionError("should not reconnect")

    monkeypatch.setattr(milvus_store.connections, "disconnect", fail_disconnect)
    monkeypatch.setattr(milvus_store, "connect_milvus", fail_connect)

    milvus_store.ensure_milvus_connected()


def test_delete_image_vectors_targets_only_image_chunks(monkeypatch):
    deleted = {}

    class DummyCollection:
        def delete(self, expr):
            deleted["expr"] = expr

    monkeypatch.setattr(milvus_store, "get_or_create_collection", lambda: DummyCollection())

    milvus_store.delete_image_vectors("CPS1000")

    assert deleted["expr"] == 'doc_id == "CPS1000" and chunk_id like "CPS1000_img_%"'
