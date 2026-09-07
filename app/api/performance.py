from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession

from app.services.performance_service import (
    calculate_session_metrics
)

from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/performance",
    tags=["Performance"]
)


@router.get("/{session_id}")
def get_session_performance(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # 1. Find the session
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

    # 3. Calculate performance
    metrics = calculate_session_metrics(
        session_id,
        db
    )

    return metrics