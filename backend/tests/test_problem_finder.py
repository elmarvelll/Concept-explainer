"""Integration tests — these need a real ingested Qdrant collection (run
`python -m rag.ingest` first) since problem_finder searches real embeddings,
not a mock. Skipped automatically if the collection isn't there yet.
"""

import json

import pytest

from rag.config import QDRANT_PATH

pytestmark = pytest.mark.skipif(not QDRANT_PATH.exists(), reason="Qdrant collection not ingested yet")


@pytest.fixture(scope="module")
def problem_finder_tool():
    from ai.tools import problem_finder

    return problem_finder


def test_retrieves_problems_related_to_subtopic(problem_finder_tool):
    result = json.loads(problem_finder_tool.invoke({"topic": "Ohm's Law", "top_k": 3}))

    assert result["success"] is True
    problems = result["data"]["problems"]
    assert 1 <= len(problems) <= 3

    for problem in problems:
        assert problem["text"]
        assert problem["textbook"]
        assert "similarity_score" in problem
        assert "complete" in problem
        # Trimmed from the LLM-facing output: chunk_id (internal-only) and
        # a difficulty field that was always null (pure token waste).
        assert "chunk_id" not in problem
        assert "difficulty" not in problem


def test_prefers_problem_like_chunks_when_available(problem_finder_tool):
    result = json.loads(problem_finder_tool.invoke({"topic": "Kirchhoff's laws", "top_k": 5}))

    assert result["success"] is True
    problems = result["data"]["problems"]
    # is_problem_like results should be sorted first.
    seen_non_problem = False
    for problem in problems:
        if not problem["is_problem_like"]:
            seen_non_problem = True
        elif seen_non_problem:
            pytest.fail("A problem-like result appeared after a non-problem-like one")


def test_unrelated_query_does_not_crash(problem_finder_tool):
    result = json.loads(problem_finder_tool.invoke({"topic": "the history of jazz music", "top_k": 2}))
    # Should still return structurally, even if results are weak — the
    # vector DB always returns *something* semantically nearest, it just
    # might not be very relevant. This asserts no crash / malformed output.
    assert "success" in result
