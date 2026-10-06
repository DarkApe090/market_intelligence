from pydantic import BaseModel

class CreateSkill(BaseModel):
    name_skill: str

class UpdateSkill(BaseModel):
    name_skill: str

class SkillResponse(BaseModel):
    id_skill: int
    name_skill: str

    model_config = {"from_attributes": True}