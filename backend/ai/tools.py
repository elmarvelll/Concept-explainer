import cmath
import json
import logging
import math
import re
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ai.calculator import CalculatorError, evaluate
from ai.circuit_solver import CircuitError, Element, solve_circuit
from rag.config import TEXTBOOK_PATH
from rag.retriever import retrieve, retrieve_with_scores
from rag.textbook_outline import load_outline
from rag.topic_finder import find_topic

logger = logging.getLogger(__name__)


# Kept deliberately small — this tool's job is to ground an explanation,
# not to hand the LLM the whole relevant section of the book. Retrieval
# itself can look broadly if needed later; what comes back to the model is
# capped and deduplicated so a handful of near-identical overlapping chunks
# (an artifact of the splitter's chunk overlap) don't multiply token cost.
SEARCH_TEXTBOOK_K = 4
MAX_PASSAGE_CHARS = 700


@tool
def search_textbook(query: str) -> str:
    """Search the electric circuits textbook for passages relevant to `query`.

    Use this whenever the user asks about a concept the textbook likely
    covers, before answering from general knowledge — ground the
    explanation in what the textbook actually says, then explain it in your
    own words rather than quoting it at length. Returns the most relevant
    passages found (possibly truncated for length), or an empty string if
    nothing relevant turned up.
    """
    results = retrieve(query, k=SEARCH_TEXTBOOK_K)
    logger.info("search_textbook(%r) -> %d passages", query, len(results))

    if not results:
        return ""

    seen: set[str] = set()
    passages = []
    for doc in results:
        text = doc.page_content.strip()
        dedup_key = text[:80]
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        if len(text) > MAX_PASSAGE_CHARS:
            text = text[:MAX_PASSAGE_CHARS].rsplit(" ", 1)[0] + " […]"
        passages.append(text)

    return "\n\n---\n\n".join(passages)


@tool
def calculator(expression: str) -> str:
    """Evaluate an exact arithmetic expression and return the numeric result.

    Use this whenever you need an exact calculation — solving a formula,
    checking an intermediate result, or answering a numeric question —
    instead of computing it yourself. Supports +, -, *, /, // , %, **,
    parentheses, decimals, and percentages (e.g. "15% * 200" or "20 + 5%").
    `expression` must be pure arithmetic — no variables or units, resolve
    those to numbers yourself before calling this.

    Returns a JSON string: {"success": true, "data": {"expression", "result"}}
    or {"success": false, "error": "..."} for an invalid expression.
    """
    try:
        result = evaluate(expression)
    except CalculatorError as e:
        logger.info("calculator(%r) failed: %s", expression, e)
        return json.dumps({"success": False, "error": str(e)})

    return json.dumps({"success": True, "data": {"expression": expression, "result": result}})


@tool
def topic_finder(topic: str) -> str:
    """Look up where `topic` sits in the textbook's table of contents.

    Use this when a student starts learning a topic (e.g. "teach me X"),
    or whenever you need to understand a topic's full scope — its
    subtopics, their order, and what comes before/after it — before
    deciding what to teach next. This reads the textbook's actual outline;
    it never invents subtopics that aren't really there.

    Returns a JSON string: {"success": true, "data": {"matched_title",
    "similarity", "breadcrumb", "subtopics", ...}} preserving the
    textbook's own hierarchy and order, or {"success": false, "error":
    "..."} if nothing in the textbook matches well enough — in that case,
    say so to the user rather than guessing a structure.
    """
    try:
        outline = load_outline()
    except FileNotFoundError as e:
        logger.warning("topic_finder(%r): %s", topic, e)
        return json.dumps({"success": False, "error": str(e)})

    result = find_topic(topic, outline)
    logger.info("topic_finder(%r) -> success=%s", topic, result["success"])
    return json.dumps(result)


# A chunk is treated as an actual exercise only if it has a numbered
# reference ("Practice Problem 2.5") or a standalone section-heading line
# ("Problems", "Review Questions", ...) — not just the word "problem(s)"
# anywhere in ordinary prose (e.g. "real-life problems of electrical
# lighting" is not an exercise), which is the false-positive the "don't
# return unrelated results just because they share a word" requirement
# specifically warns about.
_PROBLEM_NUMBER = re.compile(r"(?:practice\s+)?problem\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
_PROBLEM_HEADING = re.compile(
    r"^\s*(practice problem|problems|comprehensive problems?|review questions?|exercises?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _is_problem_like(text: str) -> bool:
    return bool(_PROBLEM_NUMBER.search(text) or _PROBLEM_HEADING.search(text))


def _looks_complete(text: str) -> bool:
    """Whether this chunk's text appears to end at a real sentence boundary
    rather than being cut off mid-problem by chunking — a chunk that isn't
    complete shouldn't have its missing tail invented."""
    return text.rstrip().endswith((".", "?", "!", '"', "'"))


@tool
def problem_finder(topic: str, subtopic: str = "", level: str = "", top_k: int = 3) -> str:
    """Find textbook problems/questions related to a topic, for use as
    worked examples, practice questions, or assessment questions.

    `topic` and `subtopic` narrow what to search for (e.g. topic="Basic
    Laws", subtopic="Kirchhoff's Current Law"); `level` is an optional
    teaching-level hint (e.g. "introductory" or "advanced") that biases
    which passages rank highest, not a literal difficulty filter — the
    textbook doesn't label problems with a difficulty rating, so this tool
    never returns one. `top_k` caps how many problems come back — this is
    the only cap that matters to you; internally more candidates are
    fetched and filtered down before you ever see them.

    Returns a JSON string: {"success": true, "data": {"problems": [...]}} —
    each problem includes its real page, chapter/section, and similarity
    score (all genuinely from the textbook/vector DB, never fabricated),
    plus `"complete": false` if the retrieved text looks cut off — say so to
    the user rather than inventing the missing part — or {"success": false,
    "error": "..."} if nothing relevant was found.
    """
    query = " ".join(part for part in (topic, subtopic, level) if part).strip() or topic

    try:
        # Overfetch internally, then rank/dedupe/trim so only the requested
        # number of genuine results — never the raw candidate pool — reaches
        # the model.
        scored = retrieve_with_scores(query, k=max(top_k * 4, 12))
    except Exception as e:
        logger.exception("problem_finder(%r) retrieval failed", query)
        return json.dumps({"success": False, "error": f"Retrieval failed: {e}"})

    problems = []
    seen: set[str] = set()
    for doc, score in scored:
        text = doc.page_content.strip()
        dedup_key = text[:120]
        if dedup_key in seen:
            continue  # an overlapping duplicate of a chunk already seen
        seen.add(dedup_key)

        number_match = _PROBLEM_NUMBER.search(text)
        problems.append(
            {
                "is_problem_like": _is_problem_like(text),
                "problem_number": number_match.group(1) if number_match else None,
                "text": text,
                "complete": _looks_complete(text),
                "textbook": TEXTBOOK_PATH.stem,
                "chapter": doc.metadata.get("chapter"),
                "section": doc.metadata.get("section"),
                "page": doc.metadata.get("page_label") or doc.metadata.get("page"),
                "similarity_score": round(score, 4),
            }
        )

    problems.sort(key=lambda p: not p["is_problem_like"])
    top = problems[:top_k]

    logger.info("problem_finder(%r) -> %d/%d problem-like results", query, sum(p["is_problem_like"] for p in top), len(top))

    if not top:
        return json.dumps({"success": False, "error": f"No problems found relevant to {query!r}"})

    return json.dumps({"success": True, "data": {"query": query, "problems": top}})


class CircuitElementInput(BaseModel):
    type: Literal["R", "L", "C", "V", "I"] = Field(
        description="R=resistor, L=inductor, C=capacitor, V=independent voltage source, I=independent current source"
    )
    name: str = Field(description="A unique label, e.g. 'R1' or 'Vs'")
    node_pos: str = Field(description="The '+' terminal's node name — '0' is always ground")
    node_neg: str = Field(description="The '-' terminal's node name — '0' is always ground")
    value: float = Field(description="Ohms for R, henries for L, farads for C, volts for V, amps for I")
    phase_degrees: float = Field(default=0.0, description="Source phase angle; only meaningful for V/I in AC analysis")


def _format_phasor(value: complex | float, is_ac: bool) -> dict | float:
    if not is_ac:
        return round(value, 6)
    return {
        "real": round(value.real, 6),
        "imag": round(value.imag, 6),
        "magnitude": round(abs(value), 6),
        "phase_degrees": round(math.degrees(cmath.phase(value)), 3),
    }


@tool
def circuit_solver(elements: list[CircuitElementInput], frequency_hz: float = 0.0) -> str:
    """Solve a circuit of arbitrary topology (multiple loops/nodes, several
    sources, resistors combined with inductors/capacitors) for every node
    voltage and voltage-source current, using nodal analysis (Kirchhoff's
    laws solved simultaneously) — not simple series/parallel reduction.

    Use this for anything the calculator can't do alone: a circuit with more
    than one loop, a bridge/mesh topology, or AC analysis. Node "0" is
    always ground (0V reference); name every other node however you like.
    Set frequency_hz=0 for DC (model an inductor as a 0-ohm wire and omit
    capacitors instead of including them at DC). Set frequency_hz to a
    positive value for AC/phasor analysis — then L and C get their
    frequency-dependent impedance, and a source's `value`/`phase_degrees`
    are its magnitude and phase.

    Returns a JSON string: {"success": true, "data": {"node_voltages": {...},
    "source_currents": {...}}} (plain numbers for DC, {"real", "imag",
    "magnitude", "phase_degrees"} for AC), or {"success": false, "error":
    "..."} for an invalid netlist (no ground reference, a short, an
    inductor/capacitor used without an AC frequency, etc.) — explain the
    error to the user rather than guessing an answer.
    """
    try:
        parsed = [Element(e.type, e.name, e.node_pos, e.node_neg, e.value, e.phase_degrees) for e in elements]
        result = solve_circuit(parsed, frequency_hz=frequency_hz)
    except CircuitError as e:
        logger.info("circuit_solver failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})

    is_ac = result["is_ac"]
    return json.dumps(
        {
            "success": True,
            "data": {
                "is_ac": is_ac,
                "frequency_hz": result["frequency_hz"],
                "node_voltages": {k: _format_phasor(v, is_ac) for k, v in result["node_voltages"].items()},
                "source_currents": {k: _format_phasor(v, is_ac) for k, v in result["source_currents"].items()},
            },
        }
    )


def make_update_learning_state_tool(user_id: str, db):
    """Builds an update_learning_state tool bound to one request's user_id
    and DB session — this can't be a module-level singleton like the other
    tools since it needs to know who's asking. See ai/models.py for where
    this gets built per-request, and learning_state.py for the single write
    path this calls into.

    This is the only place this app updates a student's pedagogical
    progress, and it happens as an ordinary tool call within the agent's
    existing tool-calling turn — no separate summarization LLM call.
    """

    @tool
    async def update_learning_state(
        topic: str,
        current_section: str | None = None,
        goal: str | None = None,
        concepts_covered_add: list[str] | None = None,
        concepts_understood_add: list[str] | None = None,
        concepts_not_understood_add: list[str] | None = None,
        misconceptions_add: list[str] | None = None,
        current_level: Literal["foundation", "core", "application", "advanced"] | None = None,
        learning_stage: Literal[
            "NEEDS_TOPIC",
            "NEEDS_DIAGNOSIS",
            "INTRODUCING_CONCEPT",
            "EXPLAINING",
            "WORKED_EXAMPLE",
            "STUDENT_PRACTICE",
            "EVALUATING",
            "RE_TEACHING",
            "READY_FOR_NEXT_CONCEPT",
            "COMPLETED",
        ]
        | None = None,
        last_question: str | None = None,
        last_problem: str | None = None,
        next_step: str | None = None,
        progress: str | None = None,
    ) -> str:
        """Record what changed about the student's learning progress for `topic`.

        Call this when something pedagogically meaningful actually
        happened — a concept was covered, understood, or misunderstood; the
        level or teaching stage changed; you decided what to teach next —
        not on every single message. Leave a parameter unset if it hasn't
        changed; this is a partial update, not a full overwrite. Use the
        exact topic title from topic_finder's `matched_title`, not your own
        paraphrase, so this student's progress on this topic is found again
        next session instead of silently starting a new one. Only mark a
        concept understood based on real evidence (a correct answer, a
        solid explanation from the student, an explicit statement) — never
        just because you explained it.

        Returns a JSON string {"success": true} or {"success": false,
        "error": "..."}.
        """
        from learning_state import upsert_state

        try:
            await upsert_state(
                db,
                user_id,
                topic,
                current_section=current_section,
                goal=goal,
                concepts_covered_add=concepts_covered_add or [],
                concepts_understood_add=concepts_understood_add or [],
                concepts_not_understood_add=concepts_not_understood_add or [],
                misconceptions_add=misconceptions_add or [],
                current_level=current_level,
                learning_stage=learning_stage,
                last_question=last_question,
                last_problem=last_problem,
                next_step=next_step,
                progress=progress,
            )
        except Exception as e:
            logger.exception("update_learning_state(%r) failed", topic)
            return json.dumps({"success": False, "error": str(e)})

        return json.dumps({"success": True})

    return update_learning_state
