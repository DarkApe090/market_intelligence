from pydantic import BaseModel

class CreateSource(BaseModel):
    name_source: str 
    id_location: int

class UpdateSource(BaseModel):
    name_source: str
    id_location: int

class SourceResponse(BaseModel):
    id_source: int
    name_source: str
    id_location: int 

    model_config = {"from_attributes" : True}