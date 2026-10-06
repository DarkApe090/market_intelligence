from fastapi import BackgroundTasks, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.schemas.Company import (CreateCompany, UpdateCompany, CompanyResponse, FindEmailRequest)
from app.services.Company import (create_company, get_company, get_companies, update_company, delete_company)
from app.services.ContactEnrichment import enrich_company


router = APIRouter(
    prefix = "/companies",
    tags = ["Companies"]
)

@router.post("/", response_model = CompanyResponse)
def create(company: CreateCompany, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    return create_company(db, company, user)

@router.get("/{id_company}", response_model = CompanyResponse)
def get(id_company: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    company = get_company(db, id_company, user)

    if company is None: 
        raise HTTPException(
            status_code = 404,
            detail = "Company not found"
        )

    return company

@router.get("/", response_model= list[CompanyResponse])
def get_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    return get_companies(db, user)

@router.put("/{id_company}", response_model = CompanyResponse)
def update(
    id_company: int,
    company: UpdateCompany,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    updated_company = update_company(
        db,
        id_company,
        company,
        user,
    )

    if updated_company is None:
        raise HTTPException(
            status_code = 404,
            detail = "Company not found"
        )

    return updated_company

@router.post("/{id_company}/find-email", status_code = 202)
def find_email(
    id_company: int,
    request: FindEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    if get_company(db, id_company, user) is None:
        raise HTTPException(
            status_code = 404,
            detail = "Company not found"
        )

    background_tasks.add_task(enrich_company, id_company, request.website_url, True)

    return {"message": "Pesquisa de email iniciada"}

@router.delete("/{id_company}")
def delete(id_company: int , db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    deleted = delete_company(db, id_company, user)

    if not deleted:
        raise HTTPException(
            status_code = 404,
            detail = "Company not found"
        )

    return {"message": "Company deleted successfully"}