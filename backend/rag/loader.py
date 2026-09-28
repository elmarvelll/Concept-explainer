import logging

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from rag.config import TEXTBOOK_PATH

logger = logging.getLogger(__name__)


def load_documents() -> list[Document]:
    """Load the textbook PDF, one Document per page."""
    if not TEXTBOOK_PATH.exists():
        raise FileNotFoundError(f"Textbook not found at {TEXTBOOK_PATH}")

    logger.info("Loading %s", TEXTBOOK_PATH.name)
    documents = PyPDFLoader(str(TEXTBOOK_PATH)).load()

    logger.info("Loaded %d pages", len(documents))
    return documents
