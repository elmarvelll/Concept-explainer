"""Pure-logic tests — no DB, no async fixtures (kept separate from
test_learning_state.py's DB integration tests so these stay plain sync
tests with nothing to trip pytest's async-fixture warnings)."""

from learning_state import _merge_unique, format_state_block


def test_merge_unique_dedupes_preserves_order_and_caps():
    result = _merge_unique(["a", "b"], ["b", "c", "d"], limit=3)
    assert result == ["b", "c", "d"]


def test_format_state_block_when_none():
    block = format_state_block(None)
    assert "none yet" in block.lower()


def test_format_state_block_includes_populated_fields():
    class FakeState:
        topic = "Fourier Transform"
        currentSection = "18.1 Introduction"
        currentLevel = "foundation"
        learningStage = "EXPLAINING"
        goal = "Understand the Fourier Transform"
        conceptsCovered = ["time domain"]
        conceptsUnderstood: list = []
        conceptsNotUnderstood = ["frequency-domain meaning"]
        misconceptions: list = []
        lastProblem = None
        nextStep = "Explain frequency-domain representation with an example"

    block = format_state_block(FakeState())
    assert "Fourier Transform" in block
    assert "18.1 Introduction" in block
    assert "frequency-domain meaning" in block
    assert "Explain frequency-domain representation" in block
    # Fields left empty/None shouldn't appear as noise.
    assert "Last problem given" not in block


def test_format_state_block_lists_paused_topics_when_no_active_state():
    block = format_state_block(None, paused_topics=["Chapter 18 Fourier Transform"])
    assert "Chapter 18 Fourier Transform" in block
    assert "update_learning_state" in block


def test_format_state_block_lists_paused_topics_alongside_active_state():
    class FakeState:
        topic = "Laplace Transform"
        currentSection = None
        currentLevel = None
        learningStage = None
        goal = None
        conceptsCovered: list = []
        conceptsUnderstood: list = []
        conceptsNotUnderstood: list = []
        misconceptions: list = []
        lastProblem = None
        nextStep = None

    block = format_state_block(FakeState(), paused_topics=["Chapter 18 Fourier Transform"])
    assert 'topic: "Laplace Transform"' in block
    assert "Chapter 18 Fourier Transform" in block
