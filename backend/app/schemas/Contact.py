from typing import Literal

from pydantic import BaseModel, EmailStr

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
    outreach_status: Literal["to_contact", "sent", "replied", "no_email"]

class OutreachStatusUpdate(BaseModel):
    outreach_status: Literal["to_contact", "sent", "replied", "no_email"]