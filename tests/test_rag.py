import pytest

from ticket_triage.rag import search_docs


def test_search_docs_returns_top_k_results():
    results = search_docs("shipping time", top_k=3)
    assert len(results) == 3


def test_search_docs_result_has_text_and_source_fields():
    results = search_docs("return policy", top_k=1)
    assert "text" in results[0]
    assert "source" in results[0]


def test_search_docs_top_result_is_relevant_to_query():
    results = search_docs("I cannot log in to my account", top_k=3)
    top_sources = [r["source"] for r in results]
    assert "Account and Login Issues" in top_sources


def test_search_docs_respects_top_k():
    results = search_docs("payment failed", top_k=2)
    assert len(results) == 2
