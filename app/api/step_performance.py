from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance

from app.schemas.step_performance import (
    StepPerformanceCreate,
    StepPerformanceResponse
)

from app.config.constants import STEPS
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/api/step-performance",
    tags=["Step Performance"]
)


@router.post(
    "/",
    response_model=StepPerformanceResponse
)
def create_step_performance(
    performance_data: StepPerformanceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Check session
    session = db.query(TrainingSession).filter(
        TrainingSession.id == performance_data.session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Security check:
    # The session must belong to the logged-in user.
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this session"
        )

    # Validate step ID
    if performance_data.step_id not in STEPS:
        raise HTTPException(
            status_code=400,
            detail="Invalid step_id. Must be between 0 and 15."
        )

    # Check whether this step already exists
    existing_step = db.query(StepPerformance).filter(
        StepPerformance.session_id ==
        performance_data.session_id,
        StepPerformance.step_id ==
        performance_data.step_id
    ).first()

    if existing_step:
        raise HTTPException(
            status_code=400,
            detail="Performance for this step already exists in this session"
        )

    step_performance = StepPerformance(
        session_id=performance_data.session_id,
        step_id=performance_data.step_id,
        step_name=STEPS[performance_data.step_id],
        attempts=performance_data.attempts,
        mistakes=performance_data.mistakes,
        first_attempt_correct=
            performance_data.first_attempt_correct,
        step_time_seconds=
            performance_data.step_time_seconds,
        completed=performance_data.completed
    )

    db.add(step_performance)
    db.commit()
    db.refresh(step_performance)

    return step_performance