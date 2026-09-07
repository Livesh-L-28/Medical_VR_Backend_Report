from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.training_report import TrainingReport
from app.services.progress_service import save_progress_history

from app.services.performance_service import calculate_session_metrics



def generate_training_report(
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
            detail="Training session not found"
        )

    # 2. Make sure this is a TRAINING session
    if session.session_type != "TRAINING":
        raise HTTPException(
            status_code=400,
            detail="Training report can only be generated for TRAINING sessions"
        )

    # 3. Get the user
    user = db.query(User).filter(
        User.id == session.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # 4. Calculate performance metrics
    metrics = calculate_session_metrics(
        session_id=session_id,
        db=db
    )

    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail="Performance metrics not found"
        )

    # 5. Calculate accuracy
    total_steps = metrics["total_steps"]
    correct_steps = metrics["correct_steps"]

    if total_steps > 0:
        accuracy = (correct_steps / total_steps) * 100
    else:
        accuracy = 0

    # 6. Calculate overall result
    if metrics["completed_steps"] < total_steps:
        if accuracy >= 50:
            overall_result = "INCOMPLETE"
        else:
            overall_result = "NEEDS_PRACTICE"

    elif accuracy >= 80 and metrics["total_mistakes"] == 0:
        overall_result = "EXCELLENT"

    elif accuracy >= 60:
        overall_result = "SATISFACTORY"

    else:
        overall_result = "NEEDS_PRACTICE"

    # 7. Check whether report already exists
    existing_report = db.query(TrainingReport).filter(
        TrainingReport.session_id == session_id
    ).first()

    if existing_report:
        save_progress_history(session_id, db)
        return existing_report

    # 8. Create training report
    report = TrainingReport(
        session_id=session.id,
        user_id=session.user_id,
        session_number=session.session_number,

        total_steps=total_steps,
        completed_steps=metrics["completed_steps"],
        correct_steps=correct_steps,

        accuracy=round(accuracy, 2),

        total_attempts=metrics["total_attempts"],
        total_mistakes=metrics["total_mistakes"],

        first_attempt_correct_count=metrics[
            "first_attempt_correct_count"
        ],

        first_attempt_accuracy=round(
            metrics["first_attempt_accuracy"],
            2
        ),

        total_time_seconds=metrics[
            "total_time_seconds"
        ],

        average_step_time_seconds=round(
            metrics["average_step_time_seconds"],
            2
        ),

        overall_result=overall_result
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    # Save progress history automatically
    save_progress_history(session_id, db)

    return report