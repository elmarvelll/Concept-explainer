"""Builds the textbook's hierarchical outline (chapters/sections/subsections)
from the PDF's own embedded bookmarks — not a hardcoded or guessed structure
— and saves it to rag/textbook_outline.json.

This only needs to run when the textbook changes, not on every question, so
it's driven from rag/ingest.py rather than from a request path. See
rag/topic_finder.py for how the agent reads this file back.

Run manually:

    python -m rag.textbook_outline
"""

import json
import logging
import re
from pathlib import Path
from typing import Callable

from pypdf import PdfReader

from rag.config import TEXTBOOK_PATH

logger = logging.getLogger(__name__)

OUTLINE_PATH = Path(__file__).resolve().parent / "textbook_outline.json"

# Matches a leading chapter/section number like "2.5 " or "Chapter 2 " at the
# start of a bookmark title, so it can be pulled out as structured data
# instead of staying buried in the title string.
_NUMBER_PATTERN = re.compile(r"^(?:Chapter\s+)?(\d+(?:\.\d+)*)\s+", re.IGNORECASE)


def _extract_number(title: str) -> str | None:
    """Pull a leading "2.5" / "Chapter 2" style number out of a title, if any."""
    match = _NUMBER_PATTERN.match(title.strip())
    return match.group(1) if match else None


def walk_outline(items: list, get_page: Callable, level: int = 1) -> list[dict]:
    """Convert a pypdf-style nested outline (or any equivalent structure of
    objects with a `.title` and a resolvable page via `get_page`) into our
    JSON schema, preserving hierarchy and order.

    `items` is a list where each element is either a bookmark-like object
    (has `.title`) or a nested list belonging to the previous sibling
    (pypdf's convention for representing a bookmark's children). `get_page`
    resolves a bookmark object to its 0-indexed page number, or None if it
    can't be resolved — kept as a separate argument (rather than calling
    `reader.get_destination_page_number` directly) so this function can be
    unit-tested without a real PDF.
    """
    nodes: list[dict] = []
    i = 0
    while i < len(items):
        item = items[i]
        if isinstance(item, list):
            # A children list belongs to the node we just appended, but if
            # the outline is malformed and starts with a list, drop it — a
            # sub-outline needs a parent to attach to.
            if nodes:
                nodes[-1]["children"] = walk_outline(item, get_page, level + 1)
            i += 1
            continue

        title = str(item.title).strip() if getattr(item, "title", None) else "Untitled"
        try:
            page = get_page(item)
        except Exception:
            logger.warning("Could not resolve page for bookmark %r", title)
            page = None

        nodes.append(
            {
                "title": title,
                "number": _extract_number(title),
                "level": level,
                "page": page,
                "children": [],
            }
        )
        i += 1

    return nodes


def generate_outline() -> dict:
    """Read the textbook's embedded PDF bookmarks and build the outline."""
    if not TEXTBOOK_PATH.exists():
        raise FileNotFoundError(f"Textbook not found at {TEXTBOOK_PATH}")

    logger.info("Reading bookmarks from %s", TEXTBOOK_PATH.name)
    reader = PdfReader(str(TEXTBOOK_PATH))

    if not reader.outline:
        raise ValueError(
            f"{TEXTBOOK_PATH.name} has no embedded bookmarks/outline — "
            "can't build a table of contents from it."
        )

    chapters = walk_outline(reader.outline, reader.get_destination_page_number)
    outline = {"textbook": TEXTBOOK_PATH.stem, "chapters": chapters}

    logger.info("Built outline with %d top-level entries", len(chapters))
    return outline


def save_outline(outline: dict, path: Path = OUTLINE_PATH) -> None:
    path.write_text(json.dumps(outline, indent=2))
    logger.info("Saved outline to %s", path)


def load_outline(path: Path = OUTLINE_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"No outline at {path} — run `python -m rag.textbook_outline` (or rag.ingest) first."
        )
    return json.loads(path.read_text())


def _flatten(nodes: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for node in nodes:
        flat.append(node)
        flat.extend(_flatten(node.get("children", [])))
    return flat


# Some textbooks nest "Chapter N" headings under a coarser "Part N" grouping
# at level 1 (this one does), so "chapter" can't just mean "the level-1
# ancestor" — it means the nearest heading that's actually titled "Chapter".
_CHAPTER_TITLE = re.compile(r"^chapter\b", re.IGNORECASE)


def find_section_for_page(page: int, outline: dict) -> dict:
    """Return the chapter/section titles that page `page` (0-indexed) falls
    under, by finding the last heading at or before it — real, derived data,
    not a guess. Used to tag chunks with their real location at ingest time
    (see rag/ingest.py) rather than invented metadata.
    """
    dated = sorted((n for n in _flatten(outline.get("chapters", [])) if n["page"] is not None), key=lambda n: n["page"])

    chapter = None
    section = None
    for node in dated:
        if node["page"] > page:
            break
        if _CHAPTER_TITLE.match(node["title"]):
            chapter = node["title"]
        section = node["title"]

    return {"chapter": chapter, "section": section}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    save_outline(generate_outline())
