from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    REAL,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SelfProfile(Base):
    __tablename__ = "self_profile"
    __table_args__ = (CheckConstraint("id = 1", name="ck_self_profile_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text)
    communication_style: Mapped[str | None] = mapped_column(Text)
    sensitivities: Mapped[dict | list | None] = mapped_column(JSON)
    goals: Mapped[dict | list | None] = mapped_column(JSON)
    profile_json: Mapped[dict | list | None] = mapped_column(JSON)
    updated_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class LifeStage(Base):
    __tablename__ = "life_stage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    kind: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Date)
    ended_at: Mapped[str | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int | None] = mapped_column(Integer)


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[dict | list | None] = mapped_column(JSON)
    bio: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict | list | None] = mapped_column(JSON)
    photo_path: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class Entity(Base):
    __tablename__ = "entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class EntityMember(Base):
    __tablename__ = "entity_member"
    __table_args__ = (UniqueConstraint("entity_id", "person_id", name="uq_entity_member_entity_person"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Date)
    ended_at: Mapped[str | None] = mapped_column(Date)


class Relationship(Base):
    __tablename__ = "relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_id: Mapped[int | None] = mapped_column(Integer)
    to_type: Mapped[str] = mapped_column(Text, nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Date)
    ended_at: Mapped[str | None] = mapped_column(Date)
    updated_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class PersonStage(Base):
    __tablename__ = "person_stage"
    __table_args__ = (UniqueConstraint("person_id", "stage_id", name="uq_person_stage_person_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("life_stage.id", ondelete="CASCADE"), nullable=False)
    role_in_stage: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Date)
    ended_at: Mapped[str | None] = mapped_column(Date)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[str | None] = mapped_column(Date)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    participants: Mapped[dict | list | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(Text)
    source_session_id: Mapped[int | None] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    chat_model: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    ended_at: Mapped[str | None] = mapped_column(TIMESTAMP)


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_used: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class Extraction(Base):
    __tablename__ = "extraction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("chat_session.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None] = mapped_column(REAL)
    status: Mapped[str | None] = mapped_column(Text, server_default="pending")
    applied_at: Mapped[str | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class Note(Base):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
