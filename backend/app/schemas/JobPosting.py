from pydantic import BaseModel

class CreateJobPosting(BaseModel):
    position_jobPosting: str 
    id_source: int 
    url_jobPosting: str | None = None

class UpdateJobPosting(BaseModel):
    position_jobPosting: str
    id_source: int 
    url_jobPosting: str | None = None

class JobPostingResponse(BaseModel):
    id_jobPosting: int
    position_jobPosting: str
    id_source: int 
    url_jobPosting: str | None = None

    model_config={"from_attributes": True}
