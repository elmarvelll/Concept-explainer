import logging

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from rag.config import COLLECTION_NAME, QDRANT_PATH
from rag.embeddings import FastEmbedEmbeddings

logger = logging.getLogger(__name__)

DEFAULT_K = 5

# Opens the collection ingest.py builds (run `python -m rag.ingest` first —
# this raises if it hasn't been run yet, since there's nothing to open).
# Created once and reused across requests, same pattern as ai/models.py's
# `llm`/`agent`. Qdrant's local (on-disk) mode locks the storage directory
# exclusively per process, so this and `rag.ingest` can't run at the same
# time.
_vector_store = QdrantVectorStore.from_existing_collection(
    embedding=FastEmbedEmbeddings(),
    path=str(QDRANT_PATH),
    collection_name=COLLECTION_NAME,
)


def retrieve(query: str, k: int = DEFAULT_K) -> list[Document]:
    """Return the k textbook chunks most relevant to `query`."""
    results = _vector_store.similarity_search(query, k=k)
    logger.info("Retrieved %d chunks for query: %r", len(results), query)
    return results


def retrieve_with_scores(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Like `retrieve`, but also returns each chunk's similarity score —
    used by problem_finder to report a real relevance score instead of an
    invented one."""
    results = _vector_store.similarity_search_with_score(query, k=k)
    logger.info("Retrieved %d scored chunks for query: %r", len(results), query)
    return results
