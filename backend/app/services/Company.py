from sqlalchemy.orm import Session
from app.models.Company import Company 
from app.schemas.Company import CreateCompany, UpdateCompany
from app.models.User import User

def create_company(db:Session, company: CreateCompany, user: User) -> Company:

    db_company = Company(name_company=company.name_company, id_user=user.id_user)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)

    return db_company


def get_company(db: Session, id_company: int, user: User) -> Company | None:
    company = db.get(Company, id_company)
    return company if company is not None and company.id_user == user.id_user else None

def get_companies(db: Session, user: User) -> list[Company]:
    return db.query(Company).filter(Company.id_user == user.id_user).all()

def update_company(db: Session, id_company: int, company: UpdateCompany, user: User) -> Company | None:

    db_company = get_company(db, id_company, user)

    if db_company is None: 
        return None
    if company.name_company is not None: 
        db_company.name_company = company.name_company

    db.commit()
    db.refresh(db_company)

    return db_company

def delete_company(db:Session, id_company:int, user: User) -> bool:
    db_company = get_company(db, id_company, user)

    if db_company is None:
        return False

    db.delete(db_company)
    db.commit()

    return True 