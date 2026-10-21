from typing import Literal

from pydantic import BaseModel, Field

from app.services.CareerProfile import MAX_SEARCH_AREAS


class SaveSuggestion(BaseModel):
    company: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=250)
    url: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=250)
    email: str | None = Field(default=None, max_length=320)


class SaveSuggestionResponse(BaseModel):
    id_company: int
    id_contact: int
    id_jobPosting: int
    company_created: bool
    already_in_outreach: bool
    email: str | None = None


class DraftRequest(BaseModel):
    company: str = Field(min_length=1, max_length=150)
    title: str = Field(default="", max_length=250)
    area: str = Field(default="", max_length=150)
    cv_skills: list[str] = Field(default_factory=list, max_length=40)
    matched_skills: list[str] = Field(default_factory=list, max_length=40)
    language: Literal["en", "pt"] = "en"
    candidate_name: str | None = Field(default=None, max_length=80)
    force: bool = False


class ProfileAreaEdit(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    skills: list[str] = Field(default_factory=list, max_length=20)

    model_config = {"str_strip_whitespace": True}


class ProfileEdit(BaseModel):
    areas: list[ProfileAreaEdit] = Field(min_length=1, max_length=MAX_SEARCH_AREAS)


class DraftResponse(BaseModel):
    fit_score: int
    fit_reason: str
    subject: str | None = None
    body: str | None = None
    skipped: bool

