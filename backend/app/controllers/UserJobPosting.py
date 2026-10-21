from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.models.User import User

from app.services import Auth

from app.schemas.UserJobPosting import (
    CreateUserJobPosting,
    UpdateUserJobPosting,
    UserJobPostingResponse,
)

from app.services.UserJobPosting import (
    create_user_jobposting,
    get_user_jobposting,
    get_user_jobpostings,
    update_user_jobposting,
    mark_jobposting_as_seen,
    delete_user_jobposting,
)


router = APIRouter(
    prefix="/user-jobpostings",
    tags=["UserJobPostings"]
)


@router.post(
    "/",
    response_model=UserJobPostingResponse
)
def create(
    user_jobposting: CreateUserJobPosting,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    try:

        return create_user_jobposting(db, user.id_user, user_jobposting)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/",
    response_model=list[UserJobPostingResponse]
)
def get_all(
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    return get_user_jobpostings(
        db,
        user.id_user
    )


@router.get(
    "/{id_jobPosting}",
    response_model=UserJobPostingResponse
)
def get(
    id_jobPosting: int,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    user_jobposting = get_user_jobposting(
        db,
        user.id_user,
        id_jobPosting
    )

    if user_jobposting is None:
        raise HTTPException(
            status_code=404,
            detail="UserJobPosting not found"
        )

    return user_jobposting


@router.put(
    "/{id_jobPosting}",
    response_model=UserJobPostingResponse
)
def update(
    id_jobPosting: int,
    user_jobposting: UpdateUserJobPosting,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    updated_user_jobposting = update_user_jobposting(
        db,
        user.id_user,
        id_jobPosting,
        user_jobposting
    )

    if updated_user_jobposting is None:
        raise HTTPException(
            status_code=404,
            detail="UserJobPosting not found"
        )

    return updated_user_jobposting


@router.patch(
    "/{id_jobPosting}/seen",
    response_model=UserJobPostingResponse
)
def mark_seen(
    id_jobPosting: int,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    user_jobposting = mark_jobposting_as_seen(
        db,
        user.id_user,
        id_jobPosting
    )

    if user_jobposting is None:
        raise HTTPException(
            status_code=404,
            detail="UserJobPosting not found"
        )

    return user_jobposting


@router.delete(
    "/{id_jobPosting}"
)
def delete(
    id_jobPosting: int,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db)
):

    deleted = delete_user_jobposting(
        db,
        user.id_user,
        id_jobPosting
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="UserJobPosting not found"
        )

    return {
        "message": "UserJobPosting deleted successfully"
    }