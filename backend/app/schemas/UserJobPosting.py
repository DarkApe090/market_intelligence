from pydantic import BaseModel
from datetime import datetime 

class CreateUserJobPosting(BaseModel):
    id_jobPosting: int


class UpdateUserJobPosting(BaseModel):
    seen_at: datetime | None = None

class UserJobPostingResponse(BaseModel):
    id_user: int
    id_jobPosting: int
    seen_at: datetime | None = None

    model_config={"from_attributes": True}