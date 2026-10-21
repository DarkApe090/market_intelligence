from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

OutreachStatus = Literal["to_contact", "sent", "replied", "no_email", "rejected"]

class CreateContact(BaseModel):
    name_contact: str | None = None
    role_contact: str | None = None
    contact_type: str | None = None
    cellphone: str | None=None
    telephone: str | None=None
    email: EmailStr | None=None
    source_url: str | None = None

class UpdateContact(BaseModel):
    name_contact: str | None = None
    role_contact: str | None = None
    contact_type: str | None = None
    cellphone: str | None=None
    telephone: str | None=None
    email: EmailStr | None=None
    source_url: str | None = None

class ContactResponse(BaseModel):
    id_contact: int
    name_contact: str | None
    role_contact: str | None
    contact_type: str | None
    cellphone: str | None
    telephone: str | None
    email: str | None
    source_url: str | None

    model_config = {"from_attributes": True}

class OutreachContactResponse(ContactResponse):
    id_company: int
    name_company: str
    website_url: str | None = None
    job_title: str | None = None
    id_jobPosting: int | None = None
    job_seen_at: datetime | None = None
    outreach_status: OutreachStatus
    sent_at: datetime | None = None

class OutreachStatusUpdate(BaseModel):
    outreach_status: OutreachStatus


class ApplyOutreachRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)

    model_config = {"str_strip_whitespace": True}


class ContactReplyResponse(BaseModel):
    sender: str = ""
    subject: str = ""
    body: str = ""
    sent_at: str | None = None
    outreach_status: OutreachStatus | None = None


class ApplyOutreachResponse(BaseModel):
    to: str