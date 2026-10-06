from typing import Literal

from pydantic import BaseModel, Field


class SaveSuggestion(BaseModel):
    company: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)
    url: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=250)


class SaveSuggestionResponse(BaseModel):
    id_company: int
    id_contact: int
    id_jobPosting: int
    company_created: bool
    already_in_outreach: bool


class DraftRequest(BaseModel):
    company: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)
    area: str = Field(default="", max_length=150)
    cv_skills: list[str] = Field(default_factory=list, max_length=40)
    matched_skills: list[str] = Field(default_factory=list, max_length=40)
    language: Literal["en", "pt"] = "en"
    candidate_name: str | None = Field(default=None, max_length=80)
    force: bool = False


class DraftResponse(BaseModel):
    fit_score: int
    fit_reason: str
    subject: str | None = None
    body: str | None = None
    skipped: bool

