"""The AI's compact pedagogical memory — deterministic reads/writes only, no
LLM calls in this module. This is the primary continuity mechanism for the
agent (see ai/prompts.py); conversation history remains in Message purely
for the UI/database, not as the model's main source of "what have we
covered so far."

Single write path: everything here is called either by main.py (reads) or
by ai/tools.py's update_learning_state tool (the only writer) — never
scattered across the codebase, so there's one place to reason about how
this data changes.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import LearningState

# Keeps concept/misconception lists bounded — this is meant to be a compact
# pedagogical summary, not an unbounded log of everything ever mentioned.
MAX_LIST_ITEMS = 12


async def load_active_state(db: AsyncSession, user_id: str) -> LearningState | None:
    """The student's current topic's state, if they have one."""
    result = await db.execute(select(LearningState).where(LearningState.userId == user_id, LearningState.isActive))
    return result.scalar_one_or_none()


async def list_paused_topics(db: AsyncSession, user_id: str) -> list[str]:
    """Other topics this student has started but isn't currently on — just
    titles, kept cheap and deterministic, so the agent can recognize "let's
    go back to X" as resuming existing progress (call update_learning_state
    with that exact title) rather than rediscovering it via topic_finder as
    if it were brand new.
    """
    result = await db.execute(
        select(LearningState.topic).where(LearningState.userId == user_id, ~LearningState.isActive)
    )
    return [row[0] for row in result.all()]


def format_state_block(state: LearningState | None, paused_topics: list[str] | None = None) -> str:
    """Compact text injected into the agent's context each turn — this is
    what replaces "read the whole conversation to figure out where we are.\""""
    paused = [t for t in (paused_topics or []) if not state or t != state.topic]

    if state is None:
        if paused:
            return (
                "Student learning state: no active topic right now. Paused progress exists on: "
                f"{', '.join(paused)}. If the student's message refers to one of these, resume it "
                "with update_learning_state using that exact title rather than starting fresh."
            )
        return "Student learning state: none yet. This student hasn't started a topic with this tutor before."

    lines = [f'Student learning state — topic: "{state.topic}"']
    if state.currentSection:
        lines.append(f"- Current section: {state.currentSection}")
    if state.currentLevel:
        lines.append(f"- Level: {state.currentLevel}")
    if state.learningStage:
        lines.append(f"- Stage: {state.learningStage}")
    if state.goal:
        lines.append(f"- Goal: {state.goal}")
    if state.conceptsCovered:
        lines.append(f"- Covered: {', '.join(state.conceptsCovered)}")
    if state.conceptsUnderstood:
        lines.append(f"- Understood: {', '.join(state.conceptsUnderstood)}")
    if state.conceptsNotUnderstood:
        lines.append(f"- Struggling with: {', '.join(state.conceptsNotUnderstood)}")
    if state.misconceptions:
        lines.append(f"- Misconceptions to correct: {', '.join(state.misconceptions)}")
    if state.lastProblem:
        lines.append(f"- Last problem given: {state.lastProblem}")
    if state.nextStep:
        lines.append(f"- Planned next step: {state.nextStep}")
    if paused:
        lines.append(
            f"- Also has paused progress on: {', '.join(paused)} (resume via update_learning_state "
            "using that exact title if the student refers to one of these, rather than starting fresh)"
        )
    return "\n".join(lines)


def _merge_unique(existing: list, additions: list, limit: int = MAX_LIST_ITEMS) -> list:
    merged = list(existing)
    for item in additions:
        if item and item not in merged:
            merged.append(item)
    return merged[-limit:]


async def upsert_state(
    db: AsyncSession,
    user_id: str,
    topic: str,
    *,
    current_section: str | None = None,
    goal: str | None = None,
    concepts_covered_add: list[str] = (),
    concepts_understood_add: list[str] = (),
    concepts_not_understood_add: list[str] = (),
    misconceptions_add: list[str] = (),
    current_level: str | None = None,
    learning_stage: str | None = None,
    last_question: str | None = None,
    last_problem: str | None = None,
    next_step: str | None = None,
    progress: str | None = None,
) -> LearningState:
    """Create-or-update this student's state for `topic`, touching only the
    fields actually provided, and make it the active topic — switching
    topics deactivates whichever one was active before rather than merging
    the two, so progress never bleeds between topics.
    """
    result = await db.execute(select(LearningState).where(LearningState.userId == user_id, LearningState.topic == topic))
    state = result.scalar_one_or_none()

    if state is None:
        state = LearningState(
            userId=user_id,
            topic=topic,
            conceptsCovered=[],
            conceptsUnderstood=[],
            conceptsNotUnderstood=[],
            misconceptions=[],
        )
        db.add(state)

    if current_section is not None:
        state.currentSection = current_section
    if goal is not None:
        state.goal = goal
    if current_level is not None:
        state.currentLevel = current_level
    if learning_stage is not None:
        state.learningStage = learning_stage
    if last_question is not None:
        state.lastQuestion = last_question
    if last_problem is not None:
        state.lastProblem = last_problem
    if next_step is not None:
        state.nextStep = next_step
    if progress is not None:
        state.progress = progress

    if concepts_covered_add:
        state.conceptsCovered = _merge_unique(state.conceptsCovered, concepts_covered_add)
    if concepts_understood_add:
        state.conceptsUnderstood = _merge_unique(state.conceptsUnderstood, concepts_understood_add)
        # Demonstrating understanding resolves it out of "not understood".
        state.conceptsNotUnderstood = [c for c in state.conceptsNotUnderstood if c not in concepts_understood_add]
    if concepts_not_understood_add:
        state.conceptsNotUnderstood = _merge_unique(state.conceptsNotUnderstood, concepts_not_understood_add)
    if misconceptions_add:
        state.misconceptions = _merge_unique(state.misconceptions, misconceptions_add)

    state.isActive = True
    state.updatedAt = datetime.now(timezone.utc)

    # At most one active topic per student.
    await db.execute(
        update(LearningState).where(LearningState.userId == user_id, LearningState.topic != topic).values(isActive=False)
    )

    await db.commit()
    await db.refresh(state)
    return state
