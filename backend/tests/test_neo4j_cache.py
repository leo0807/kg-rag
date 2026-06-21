"""Unit tests for the optional Neo4j query cache layer."""
import time
from unittest.mock import MagicMock, call

from src.services.retrieval.neo4j_cache import (
    _QueryCache,
    _CachedSession,
    _is_write_query,
    _make_cache_key,
    get_cache,
)


def _make_session(rows: list[dict] | None = None):
    session = MagicMock()
    session.run.return_value = rows or [{"id": "CPS1000"}]
    return session


class TestIsWriteQuery:
    def test_match_is_read(self):
        assert _is_write_query("MATCH (n) RETURN n") is False

    def test_create_is_write(self):
        assert _is_write_query("CREATE (n:Document {name: 'x'})") is True

    def test_merge_is_write(self):
        assert _is_write_query("MERGE (n:Document {id: $id})") is True

    def test_set_is_write(self):
        assert _is_write_query("MATCH (n) SET n.flag = true") is True

    def test_delete_is_write(self):
        assert _is_write_query("MATCH (n) DELETE n") is True

    def test_case_insensitive(self):
        assert _is_write_query("create (n) return n") is True


class TestMakeCacheKey:
    def test_same_query_same_key(self):
        k1 = _make_cache_key("MATCH (n) RETURN n", {})
        k2 = _make_cache_key("MATCH (n) RETURN n", {})
        assert k1 == k2

    def test_different_query_different_key(self):
        k1 = _make_cache_key("MATCH (a) RETURN a", {})
        k2 = _make_cache_key("MATCH (b) RETURN b", {})
        assert k1 != k2

    def test_different_params_different_key(self):
        k1 = _make_cache_key("MATCH (n {id: $id}) RETURN n", {"id": "A"})
        k2 = _make_cache_key("MATCH (n {id: $id}) RETURN n", {"id": "B"})
        assert k1 != k2

    def test_param_order_does_not_matter(self):
        k1 = _make_cache_key("Q", {"a": 1, "b": 2})
        k2 = _make_cache_key("Q", {"b": 2, "a": 1})
        assert k1 == k2


class TestQueryCache:
    def test_get_returns_none_on_miss(self):
        cache = _QueryCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        cache = _QueryCache()
        cache.set("key1", [{"id": "CPS1"}], ttl=60)
        assert cache.get("key1") == [{"id": "CPS1"}]

    def test_ttl_expiry(self):
        cache = _QueryCache()
        cache.set("key1", [{"id": "x"}], ttl=1)
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_max_entries_evicts_oldest(self):
        cache = _QueryCache(max_entries=2)
        cache.set("k1", [{"a": 1}], ttl=60)
        cache.set("k2", [{"b": 2}], ttl=60)
        cache.set("k3", [{"c": 3}], ttl=60)  # should evict k1
        assert cache.size == 2
        assert cache.get("k1") is None
        assert cache.get("k3") is not None

    def test_invalidate_clears_all(self):
        cache = _QueryCache()
        cache.set("k1", [{"a": 1}], ttl=60)
        cache.set("k2", [{"b": 2}], ttl=60)
        cache.invalidate()
        assert cache.size == 0

    def test_stats_tracks_hits_and_misses(self):
        cache = _QueryCache()
        cache.set("k1", [{"a": 1}], ttl=60)
        cache.get("k1")   # hit
        cache.get("k2")   # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestCachedSession:
    def test_read_query_cached_on_second_call(self):
        real_session = _make_session([{"id": "CPS1000"}])
        cache = _QueryCache()
        cs = _CachedSession(real_session, cache, ttl=60)

        cypher = "MATCH (d:Document) RETURN d.name AS id LIMIT 1"
        r1 = cs.run(cypher)
        r2 = cs.run(cypher)

        assert r1 == r2
        assert real_session.run.call_count == 1  # only called once

    def test_write_query_not_cached(self):
        real_session = _make_session()
        cache = _QueryCache()
        cs = _CachedSession(real_session, cache, ttl=60)

        cypher = "CREATE (n:Document {name: $name}) RETURN n"
        cs.run(cypher, name="CPS1")
        cs.run(cypher, name="CPS1")

        assert real_session.run.call_count == 2  # called both times

    def test_different_params_not_shared(self):
        rows_a = [{"id": "CPS1000"}]
        rows_b = [{"id": "CPS2000"}]
        call_count = [0]

        def fake_run(cypher, **params):
            call_count[0] += 1
            return rows_a if params.get("doc_id") == "CPS1000" else rows_b

        real_session = MagicMock()
        real_session.run.side_effect = fake_run

        cache = _QueryCache()
        cs = _CachedSession(real_session, cache, ttl=60)
        cypher = "MATCH (d:Document {name: $doc_id}) RETURN d"

        r1 = cs.run(cypher, doc_id="CPS1000")
        r2 = cs.run(cypher, doc_id="CPS2000")

        assert r1 != r2
        assert call_count[0] == 2

    def test_delegates_unknown_attrs_to_real_session(self):
        real_session = _make_session()
        real_session.some_attr = "value"
        cache = _QueryCache()
        cs = _CachedSession(real_session, cache, ttl=60)
        assert cs.some_attr == "value"


class TestGetCache:
    def test_returns_global_cache_instance(self):
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2
