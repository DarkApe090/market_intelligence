import ipaddress
import re
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

EMAIL_VALUE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


class CreateCompany(BaseModel):
    name_company: str 

class UpdateCompany(BaseModel):
    name_company: str | None=None

class CompanyResponse(BaseModel):
    id_company: int
    name_company: str
    website_url: str | None = None

    model_config = {"from_attributes": True}

class FindEmailRequest(BaseModel):
    website_url: str | None = None

    @field_validator("website_url")
    @classmethod
    def normalize_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None

        website = value.strip()
        if EMAIL_VALUE.fullmatch(website):
            return website.casefold()
        if not website.startswith(("http://", "https://")):
            website = f"https://{website}"

        parsed = urlparse(website)
        host = parsed.hostname or ""
        if "." not in host or parsed.username or parsed.password or len(website) > 500:
            raise ValueError("Site inválido.")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return f"{parsed.scheme}://{parsed.netloc}"
        raise ValueError("Indica o endereço do site, não um IP.")