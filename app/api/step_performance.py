from typing import List
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


@router.post(
    "/batch",
    response_model=List[StepPerformanceResponse]
)
def create_batch_step_performance(
    performances: List[StepPerformanceCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ingest multiple step performance records in a single atomic transaction.
    Allows Unity VR headsets to buffer telemetry and upload in one request.
    """
    if not performances:
        return []

    # Validate session ownership
    session_ids = {p.session_id for p in performances}
    sessions = db.query(TrainingSession).filter(TrainingSession.id.in_(session_ids)).all()
    session_map = {s.id: s for s in sessions}

    for sid in session_ids:
        if sid not in session_map:
            raise HTTPException(status_code=404, detail=f"Session {sid} not found")
        if session_map[sid].user_id != current_user.id:
            raise HTTPException(status_code=403, detail=f"Unauthorized access to session {sid}")

    # Check for duplicate step_ids in incoming payload
    seen = set()
    for p in performances:
        key = (p.session_id, p.step_id)
        if key in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate step_id {p.step_id} in payload")
        seen.add(key)
        if p.step_id not in STEPS:
            raise HTTPException(status_code=400, detail=f"Invalid step_id {p.step_id}. Must be between 0 and 15.")

    # Check for existing records in DB
    existing = db.query(StepPerformance).filter(
        StepPerformance.session_id.in_(session_ids)
    ).all()
    existing_keys = {(e.session_id, e.step_id) for e in existing}

    created_records = []
    for p in performances:
        if (p.session_id, p.step_id) in existing_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Performance for step {p.step_id} already exists in session {p.session_id}"
            )

        rec = StepPerformance(
            session_id=p.session_id,
            step_id=p.step_id,
            step_name=STEPS[p.step_id],
            attempts=p.attempts,
            mistakes=p.mistakes,
            first_attempt_correct=p.first_attempt_correct,
            step_time_seconds=p.step_time_seconds,
            completed=p.completed
        )
        db.add(rec)
        created_records.append(rec)

    db.commit()
    for rec in created_records:
        db.refresh(rec)

    return created_records