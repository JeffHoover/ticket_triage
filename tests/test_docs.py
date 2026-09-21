import pytest

from ticket_triage.docs import chunk_document


def test_chunk_document_splits_on_paragraph_boundaries():
    document = {
        "title": "Shipping Policy",
        "content": "We ship within 2 business days.\n\nOrders over $50 ship free.",
    }
    chunks = chunk_document(document)
    assert len(chunks) == 2
    assert chunks[0]["text"] == "We ship within 2 business days."
    assert chunks[1]["text"] == "Orders over $50 ship free."


def test_chunk_document_includes_source_title_in_every_chunk():
    document = {
        "title": "Return Policy",
        "content": "Returns accepted within 30 days.\n\nItems must be unused.",
    }
    chunks = chunk_document(document)
    for chunk in chunks:
        assert chunk["source"] == "Return Policy"


def test_chunk_document_excludes_empty_paragraphs():
    document = {
        "title": "FAQ",
        "content": "First paragraph.\n\n\n\nSecond paragraph.",
    }
    chunks = chunk_document(document)
    assert all(chunk["text"].strip() for chunk in chunks)
    assert len(chunks) == 2


def test_chunk_document_single_paragraph_returns_one_chunk():
    document = {
        "title": "Contact Us",
        "content": "Email support@example.com for help.",
    }
    chunks = chunk_document(document)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Email support@example.com for help."
