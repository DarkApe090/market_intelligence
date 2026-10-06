from pydantic import BaseModel

class CreateLocation(BaseModel):
    street_name: str 
    zip_code: str 
    city: str 
    district: str | None=None
    parish: str | None=None
    county: str | None=None

class UpdateLocation(BaseModel):
    street_name: str | None = None
    zip_code: str | None = None
    city: str | None = None
    district: str | None=None
    parish: str | None=None
    county: str | None=None

class LocationResponse(BaseModel):
    id_location: int
    street_name: str
    zip_code: str
    city: str
    district: str | None
    parish: str | None
    county: str | None

    model_config = {"from_attributes": True}
