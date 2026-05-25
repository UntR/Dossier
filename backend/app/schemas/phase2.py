from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DossierModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DateFieldsModel(DossierModel):
    @field_validator("started_at", "ended_at", "occurred_at", check_fields=False, mode="before")
    @classmethod
    def empty_date_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class PersonCreate(DossierModel):
    name: str = Field(min_length=1)
    aliases: list[str] | None = None
    bio: str | None = None
    profile_json: dict[str, Any] | None = None
    photo_path: str | None = None
    importance: int = Field(default=0, ge=0, le=5)


class PersonUpdate(DossierModel):
    name: str | None = Field(default=None, min_length=1)
    aliases: list[str] | None = None
    bio: str | None = None
    profile_json: dict[str, Any] | None = None
    photo_path: str | None = None
    importance: int | None = Field(default=None, ge=0, le=5)


class PersonMergeRequest(DossierModel):
    target_person_id: int


class EntityCreate(DossierModel):
    type: Literal["company", "family", "friend_group", "org"]
    name: str = Field(min_length=1)
    bio: str | None = None
    profile_json: dict[str, Any] | None = None


class EntityUpdate(DossierModel):
    type: Literal["company", "family", "friend_group", "org"] | None = None
    name: str | None = Field(default=None, min_length=1)
    bio: str | None = None
    profile_json: dict[str, Any] | None = None


class EntityMemberCreate(DateFieldsModel):
    person_id: int
    role: str | None = None
    started_at: date | None = None
    ended_at: date | None = None


class RelationshipCreate(DateFieldsModel):
    from_type: Literal["self", "person"]
    from_id: int | None = None
    to_type: Literal["person", "entity"]
    to_id: int
    relation_type: str = Field(min_length=1)
    role: str | None = None
    strength: int | None = Field(default=None, ge=1, le=5)
    status: str | None = None
    notes: str | None = None
    started_at: date | None = None
    ended_at: date | None = None


class RelationshipUpdate(DateFieldsModel):
    from_type: Literal["self", "person"] | None = None
    from_id: int | None = None
    to_type: Literal["person", "entity"] | None = None
    to_id: int | None = None
    relation_type: str | None = Field(default=None, min_length=1)
    role: str | None = None
    strength: int | None = Field(default=None, ge=1, le=5)
    status: str | None = None
    notes: str | None = None
    started_at: date | None = None
    ended_at: date | None = None


class EventCreate(DateFieldsModel):
    occurred_at: date | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    participants: list[dict[str, Any]] | None = None
    source: str | None = None
    source_session_id: int | None = None
    importance: int = Field(default=0, ge=0, le=5)


class EventUpdate(DateFieldsModel):
    occurred_at: date | None = None
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    participants: list[dict[str, Any]] | None = None
    source: str | None = None
    source_session_id: int | None = None
    importance: int | None = Field(default=None, ge=0, le=5)


class LifeStageCreate(DateFieldsModel):
    name: str = Field(min_length=1)
    kind: str | None = None
    location: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    notes: str | None = None
    sort_order: int | None = None


class LifeStageUpdate(DateFieldsModel):
    name: str | None = Field(default=None, min_length=1)
    kind: str | None = None
    location: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    notes: str | None = None
    sort_order: int | None = None


class PersonStageCreate(DateFieldsModel):
    stage_id: int
    role_in_stage: str | None = None
    started_at: date | None = None
    ended_at: date | None = None


class SelfProfileUpdate(DossierModel):
    name: str | None = Field(default=None, min_length=1)
    bio: str | None = None
    communication_style: str | None = None
    sensitivities: list[str] | None = None
    goals: list[str] | None = None
    profile_json: dict[str, Any] | None = None
