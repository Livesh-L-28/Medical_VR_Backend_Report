from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession

from app.schemas.weak_area import WeakAreaResponse
from app.services.weak_area_service import analyze_weak_areas
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/weak-areas",
    tags=["Weak Areas"]
)


@router.get(
    "/{session_id}",
    response_model=list[WeakAreaResponse]
)
def get_weak_areas(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # 1. Check whether the session exists
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # 2. Check session ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    # 3. Analyze weak areas
    weak_areas = analyze_weak_areas(
        session_id,
        db
    )

    return weak_areas