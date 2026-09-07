from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.session import TrainingSession
from app.services.performance_service import calculate_session_metrics


def assess_test_session(
    session_id: int,
    db: Session
):
    # 1. Check whether the session exists
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Test session not found"
        )

    # 2. Make sure this is a TEST session
    if session.session_type != "TEST":
        raise HTTPException(
            status_code=400,
            detail="Assessment can only be performed on TEST sessions"
        )

    # 3. Calculate performance metrics
    metrics = calculate_session_metrics(
        session_id=session_id,
        db=db
    )

    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail="Performance metrics not found"
        )

    total_steps = metrics["total_steps"]
    completed_steps = metrics["completed_steps"]
    correct_steps = metrics["correct_steps"]
    total_mistakes = metrics["total_mistakes"]

    # 4. Calculate accuracy
    if total_steps > 0:
        accuracy = (correct_steps / total_steps) * 100
    else:
        accuracy = 0

    # 5. Determine PASS / FAIL
    if (
        completed_steps == 16
        and accuracy >= 80
        and total_mistakes == 0
    ):
        result = "PASS"
    else:
        result = "FAIL"

    # 6. Return deterministic assessment
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "session_number": session.session_number,
        "session_type": session.session_type,

        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "correct_steps": correct_steps,

        "accuracy": round(accuracy, 2),

        "total_attempts": metrics["total_attempts"],
        "total_mistakes": total_mistakes,

        "first_attempt_correct_count": metrics[
            "first_attempt_correct_count"
        ],

        "first_attempt_accuracy": round(
            metrics["first_attempt_accuracy"],
            2
        ),

        "total_time_seconds": metrics[
            "total_time_seconds"
        ],

        "average_step_time_seconds": round(
            metrics["average_step_time_seconds"],
            2
        ),

        "result": result
    }