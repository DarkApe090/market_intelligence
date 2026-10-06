from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.Source import ( CreateSource, UpdateSource, SourceResponse)
from app.services.Source import (create_source, get_source, get_sources, update_source, delete_source)

router = APIRouter(
    prefix="/sources",
    tags= ["Sources"]
)

@router.post("/", response_model= SourceResponse)
def create (source: CreateSource, db: Session = Depends(get_db)):
    return create_source(db, source)

@router.get("/{id_source}", response_model= SourceResponse)
def get(id_source: int, db: Session = Depends(get_db)):
    
    source = get_source(db, id_source)

    if source is None: 
        raise HTTPException(
            status_code=404,
            detail = "Source not found"
        )
    
    return source

@router.get("/", response_model=list[SourceResponse])
def get_all( db: Session = Depends (get_db)):
    return get_sources(db)

@router.put("/{id_source}", response_model= SourceResponse)
def update(
    id_source: int,
    source: UpdateSource,
    db: Session = Depends(get_db)
): 

    updated_source = update_source(
        db,
        id_source,
        source
    )

    if updated_source is None:
        raise HTTPException(
            status_code=404,
            detail="Source not found"
        )

    return updated_source

@router.delete("/{id_source}")
def delete(id_source: int, db: Session = Depends(get_db)):

    deleted = delete_source(db, id_source)

    if not deleted: 
        raise HTTPException(
            status_code= 404,
            detail = "Source not found"
        )

    return {"message": "Source deleted successfully"}