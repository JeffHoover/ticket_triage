import chromadb

from ticket_triage.docs import CORPUS, chunk_document

_collection = None


def build_collection():
    """Build an in-memory ChromaDB collection from the product-docs corpus.

    ChromaDB's default embedding function (sentence-transformers/all-MiniLM-L6-v2)
    runs locally with no API key — appropriate for a mock corpus.
    A new EphemeralClient is used so no data persists between runs.
    """
    client = chromadb.EphemeralClient()
    collection = client.create_collection("product_docs")
    chunks = [chunk for doc in CORPUS for chunk in chunk_document(doc)]
    collection.add(
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[{"source": chunk["source"]} for chunk in chunks],
        ids=[f"chunk-{i}" for i in range(len(chunks))],
    )
    return collection


def _get_collection():
    global _collection
    if _collection is None:
        _collection = build_collection()
    return _collection


def search_docs(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve the top_k most relevant chunks for query.

    The model calls this tool when it needs product-doc grounding — retrieval
    is on-demand rather than always injected on entry, so tokens are only spent
    when the model judges retrieval necessary.
    """
    results = _get_collection().query(query_texts=[query], n_results=top_k)
    return [
        {"text": document, "source": metadata["source"]}
        for document, metadata in zip(
            results["documents"][0], results["metadatas"][0]
        )
    ]
