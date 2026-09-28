"""Finds where a topic lives in the textbook's outline (rag/textbook_outline.json)
and returns its full subtree, preserving the textbook's own hierarchy and
order — this never invents subtopics, it only returns what's actually in the
outline.

Kept separate from rag/retriever.py: this answers "what is the structure of
this topic in the textbook?" (a lookup over the outline), not "what does the
textbook say?" (semantic search over chunk content) — see rag/README.md for
the full separation of responsibilities.
"""

import re
from difflib import SequenceMatcher

# Matches the same leading numbering textbook_outline.py strips out, plus
# punctuation, so "2.4 Kirchhoff's Laws" and "kirchhoffs laws" compare equal.
_LEADING_NUMBER = re.compile(r"^(?:chapter\s+)?\d+(?:\.\d+)*\s+", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^\w\s]")

DEFAULT_THRESHOLD = 0.55



def _normalize(text: str) -> str:
    text = _LEADING_NUMBER.sub("", text.strip())
    text = _PUNCTUATION.sub("", text.lower())
    return re.sub(r"\s+", " ", text).strip()



def _similarity(query: str, title: str) -> float:
    query_n, title_n = _normalize(query), _normalize(title)
    if not query_n or not title_n:
        return 0.0

    ratio = SequenceMatcher(None, query_n, title_n).ratio()
    # A direct substring match (handles simple pluralization/rewording, e.g.
    # "laplace transform" inside "laplace transforms") is a much stronger
    # signal than character-level similarity alone.
    if query_n in title_n or title_n in query_n:
        ratio = max(ratio, 0.9)
    return ratio



def _flatten(nodes: list[dict], path: tuple[str, ...] = ()) -> list[tuple[dict, tuple[str, ...]]]:
    flattened: list[tuple[dict, tuple[str, ...]]] = []
    for node in nodes:
        flattened.append((node, path))
        flattened.extend(_flatten(node.get("children", []), path + (node["title"],)))
    return flattened


def find_topic(query: str, outline: dict, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Find the outline node whose title best matches `query`.

    Returns {"success": True, "data": {...}} with the matched node's own
    subtopics (preserving order/hierarchy) and its breadcrumb of parent
    titles, or {"success": False, "error": "..."} if nothing matches well
    enough — never a fabricated structure.
    """
    candidates = _flatten(outline.get("chapters", []))
    if not candidates:
        return {"success": False, "error": "Textbook outline is empty"}

    best_node, best_path, best_score = None, (), 0.0
    for node, path in candidates:
        score = _similarity(query, node["title"])
        if score > best_score:
            best_node, best_path, best_score = node, path, score

    if best_node is None or best_score < threshold:
        return {"success": False, "error": f"Topic {query!r} not found in textbook outline"}

    return {
        "success": True,
        "data": {
            "matched_title": best_node["title"],
            "similarity": round(best_score, 3),
            "breadcrumb": list(best_path),
            "level": best_node["level"],
            "page": best_node["page"],
            "number": best_node["number"],
            "subtopics": best_node["children"],
        },
    }
