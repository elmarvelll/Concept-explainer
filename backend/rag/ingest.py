"""Reads the textbook PDF in backend/resources/, builds its outline, splits
its text into chunks, tags each chunk with its real chapter/section (from
that outline), embeds them locally, and stores the result in an on-disk
Qdrant collection for retrieval later (see retriever.py, topic_finder.py).

Run manually whenever the PDF changes — this doesn't run per-request, only
when the source textbook is added or replaced:

    python -m rag.ingest
"""

import logging

from langchain_qdrant import QdrantVectorStore

from rag.config import COLLECTION_NAME, QDRANT_PATH
from rag.embeddings import FastEmbedEmbeddings
from rag.loader import load_documents
from rag.splitter import split_documents
from rag.textbook_outline import find_section_for_page, generate_outline, save_outline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def ingest() -> None:
    outline = generate_outline()
    save_outline(outline)

    documents = load_documents()

    # Tag each page with where it actually sits in the textbook (real data,
    # derived from the outline just built) before splitting, so every chunk
    # inherits accurate chapter/section metadata — this is what lets
    # problem_finder report a chunk's real location instead of guessing.
    for doc in documents:
        doc.metadata.update(find_section_for_page(doc.metadata["page"], outline))

    chunks = split_documents(documents)

    embeddings = FastEmbedEmbeddings()

    logger.info("Embedding %d chunks into Qdrant collection %r at %s", len(chunks), COLLECTION_NAME, QDRANT_PATH)
    QdrantVectorStore.from_documents(
        chunks,
        embedding=embeddings,
        path=str(QDRANT_PATH),
        collection_name=COLLECTION_NAME,
        force_recreate=True,
    )
    logger.info("Ingestion complete")


if __name__ == "__main__":
    ingest()
