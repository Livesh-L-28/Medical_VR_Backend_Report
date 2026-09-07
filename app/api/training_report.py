from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession

from app.services.training_report_service import generate_training_report
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/training-reports",
    tags=["Training Reports"]
)


@router.post("/{session_id}")
def create_training_report(
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

    # 3. Generate the training report
    report = generate_training_report(
        session_id=session_id,
        db=db
    )

    return {
        "message": "Training report generated successfully",
        "report_id": report.id,
        "session_id": report.session_id,
        "user_id": report.user_id,
        "session_number": report.session_number,
        "total_steps": report.total_steps,
        "completed_steps": report.completed_steps,
        "correct_steps": report.correct_steps,
        "accuracy": report.accuracy,
        "total_attempts": report.total_attempts,
        "total_mistakes": report.total_mistakes,
        "first_attempt_correct_count": report.first_attempt_correct_count,
        "first_attempt_accuracy": report.first_attempt_accuracy,
        "total_time_seconds": report.total_time_seconds,
        "average_step_time_seconds": report.average_step_time_seconds,
        "overall_result": report.overall_result,
        "created_at": report.created_at
    }