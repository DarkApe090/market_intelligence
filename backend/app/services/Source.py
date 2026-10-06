from sqlalchemy.orm import Session

from app.models.Source import Source
from app.schemas.Source import CreateSource, UpdateSource


def create_source(
    db: Session,
    source: CreateSource
) -> Source:

    db_source = Source(
        name_source=source.name_source,
        id_location=source.id_location
    )

    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    return db_source


def get_source(
    db: Session,
    id_source: int
) -> Source | None:

    return db.query(Source).filter(
        Source.id_source == id_source
    ).first()


def get_sources(
    db: Session
) -> list[Source]:

    return db.query(Source).all()


def update_source(
    db: Session,
    id_source: int,
    source: UpdateSource
) -> Source | None:

    db_source = db.get(Source, id_source)

    if db_source is None:
        return None

    db_source.name_source = source.name_source
    db_source.id_location = source.id_location

    db.commit()
    db.refresh(db_source)

    return db_source


def delete_source(
    db: Session,
    id_source: int
) -> bool:

    db_source = db.get(Source, id_source)

    if db_source is None:
        return False

    db.delete(db_source)
    db.commit()

    return True