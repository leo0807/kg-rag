"""Unit tests for query expansion (file synonyms only; Neo4j driver is mocked)."""
from unittest.mock import MagicMock, patch

from src.services.retrieval.query_expander import expand_query, reload_synonyms


def _fake_driver(synonyms_by_term: dict | None = None) -> MagicMock:
    """Return a driver stub. synonyms_by_term: {term: [synonym, ...]}"""
    records = []
    if synonyms_by_term:
        for term, syns in synonyms_by_term.items():
            r = MagicMock()
            r.__getitem__ = MagicMock(side_effect=lambda k, t=term, s=syns: t if k == "term" else s)
            records.append(r)

    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.run.return_value = records

    driver = MagicMock()
    driver.session.return_value = session
    return driver


class TestExpandQueryNoSynonyms:
    def test_no_synonyms_returns_original(self):
        driver = _fake_driver()
        query, info = expand_query(driver, "密封剂的要求是什么？")
        assert query == "密封剂的要求是什么？"
        assert info == []

    def test_empty_question(self):
        driver = _fake_driver()
        query, info = expand_query(driver, "")
        assert query == ""

    def test_stop_words_only_returns_original(self):
        driver = _fake_driver()
        query, info = expand_query(driver, "要求规定如何")
        assert query == "要求规定如何"


class TestExpandQueryFileSynonyms:
    def test_file_synonym_expands_query(self):
        # regex [一-龥]{2,} extracts EACH contiguous CJK run as one token.
        # Use punctuation to separate the synonym term from the rest.
        fake_synonyms = {"密封剂": ["sealant", "PR-1422"]}
        with patch("src.services.retrieval.query_expander._load_file_synonyms", return_value=fake_synonyms):
            driver = _fake_driver()
            query, info = expand_query(driver, "密封剂，施工期限多少？")
        assert "sealant" in query or "PR-1422" in query
        assert len(info) == 1
        assert "密封剂" in info[0]

    def test_multiple_synonyms_all_included(self):
        fake_synonyms = {"钛合金": ["TC4", "Ti-6Al-4V"]}
        with patch("src.services.retrieval.query_expander._load_file_synonyms", return_value=fake_synonyms):
            driver = _fake_driver()
            # comma separates 钛合金 as its own CJK token
            query, _ = expand_query(driver, "钛合金，紧固件力矩要求")
        assert "TC4" in query
        assert "Ti-6Al-4V" in query

    def test_expansion_info_format(self):
        fake_synonyms = {"密封剂": ["sealant"]}
        with patch("src.services.retrieval.query_expander._load_file_synonyms", return_value=fake_synonyms):
            driver = _fake_driver()
            _, info = expand_query(driver, "密封剂，施工")
        assert info[0].startswith("密封剂 →")


class TestExpandQueryNeo4jFallback:
    def test_neo4j_failure_gracefully_ignored(self):
        driver = MagicMock()
        driver.session.side_effect = Exception("connection refused")
        with patch("src.services.retrieval.query_expander._load_file_synonyms", return_value={}):
            query, info = expand_query(driver, "密封剂的要求")
        assert "密封剂" in query  # original preserved
        assert info == []


class TestReloadSynonyms:
    def test_reload_clears_cache(self):
        reload_synonyms()  # should not raise
