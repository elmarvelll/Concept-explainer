from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
TEXTBOOK_PATH = RESOURCES_DIR / "_Charles_Alexander,_Matthew_Sadiku_Fundamentals_of_Electric_Circuits.pdf"

QDRANT_PATH = Path(__file__).resolve().parent / "qdrant_data"
COLLECTION_NAME = "textbook"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
