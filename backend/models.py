import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


def _new_id() -> str:
    # Prisma's `@default(cuid())` ids are generated client-side, not by the
    # DB — any unique string works for a row this service creates, the
    # format doesn't need to match Prisma's cuid algorithm.
    return uuid.uuid4().hex


# Mapped to the `User` table Prisma's schema owns (frontend/prisma/schema.prisma)
# — this service never writes to it, only joins against it for the
# Message.user relationship.
class User(Base):
    __tablename__ = "User"

    id: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str]
    name: Mapped[str | None]
    passwordHash: Mapped[str]
    # Real users are created by the frontend (Prisma) — this service never
    # writes User rows in production, only tests do (for FK setup), so this
    # default only matters there. Same NULL-default pitfall as Message's.
    createdAt: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = "Message"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    userId: Mapped[str] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=True))
    content: Mapped[str] = mapped_column(Text)
    # The column has a DB-level `DEFAULT CURRENT_TIMESTAMP(3)` from Prisma's
    # migration, but SQLAlchemy doesn't introspect that — it sends an
    # explicit NULL for an unset attribute, which violates the NOT NULL
    # constraint. Setting a Python-side default avoids that.
    createdAt: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship()


# The AI's compact pedagogical memory — see frontend/prisma/schema.prisma
# for the full design rationale. One row per (userId, topic); at most one
# `isActive=True` per user at a time (switching topics flips this rather
# than merging state). Written only by ai/tools.py's update_learning_state.
class LearningState(Base):
    __tablename__ = "LearningState"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    userId: Mapped[str] = mapped_column(ForeignKey("User.id", ondelete="CASCADE"))

    topic: Mapped[str]
    currentSection: Mapped[str | None]
    goal: Mapped[str | None] = mapped_column(Text)

    conceptsCovered: Mapped[list] = mapped_column(JSON, default=list)
    conceptsUnderstood: Mapped[list] = mapped_column(JSON, default=list)
    conceptsNotUnderstood: Mapped[list] = mapped_column(JSON, default=list)
    misconceptions: Mapped[list] = mapped_column(JSON, default=list)

    currentLevel: Mapped[str | None]
    learningStage: Mapped[str | None]

    lastQuestion: Mapped[str | None] = mapped_column(Text)
    lastProblem: Mapped[str | None] = mapped_column(Text)
    nextStep: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[str | None] = mapped_column(Text)

    isActive: Mapped[bool] = mapped_column(Boolean, default=True)

    createdAt: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # No DB-level default (Prisma's @updatedAt is applied client-side, not a
    # SQL DEFAULT) — must be set explicitly on every insert/update.
    updatedAt: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
