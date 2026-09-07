from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.progress_history import ProgressHistory

from app.services.progress_service import save_progress_history
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/progress",
    tags=["Progress"]
)


# Save progress for a session
@router.post("/{session_id}")
def create_progress(
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

    # 3. Save progress
    progress = save_progress_history(
        session_id,
        db
    )

    if progress is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return {
        "message": "Progress history saved successfully",
        "progress_id": progress.id,
        "session_id": progress.session_id,
        "user_id": progress.user_id,
        "session_number": progress.session_number,
        "accuracy": progress.accuracy,
        "total_mistakes": progress.total_mistakes,
        "total_attempts": progress.total_attempts,
        "total_time_seconds": progress.total_time_seconds,
        "completed_steps": progress.completed_steps
    }


# Get progress for a user
@router.get("/user/{user_id}")
def get_user_progress(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Check that the requested user is the logged-in user
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this user's progress"
        )

    progress_records = db.query(ProgressHistory).filter(
        ProgressHistory.user_id == current_user.id
    ).order_by(
        ProgressHistory.session_number.asc()
    ).all()

    if not progress_records:
        raise HTTPException(
            status_code=404,
            detail="No progress history found for this user"
        )

    return [
        {
            "id": progress.id,
            "session_id": progress.session_id,
            "user_id": progress.user_id,
            "session_number": progress.session_number,
            "accuracy": progress.accuracy,
            "total_mistakes": progress.total_mistakes,
            "total_attempts": progress.total_attempts,
            "total_time_seconds": progress.total_time_seconds,
            "completed_steps": progress.completed_steps,
            "created_at": progress.created_at
        }
        for progress in progress_records
    ]