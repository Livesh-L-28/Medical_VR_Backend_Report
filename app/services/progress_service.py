from sqlalchemy.orm import Session

from app.database.models.session import TrainingSession
from app.database.models.progress_history import ProgressHistory
from app.services.performance_service import calculate_session_metrics


def save_progress_history(session_id: int, db: Session):

    # 1. Get session
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        return None

    # 2. Calculate current session metrics
    metrics = calculate_session_metrics(session_id, db)

    if metrics is None:
        return None

    # 3. Calculate accuracy
    if metrics["total_steps"] > 0:
        accuracy = (
            metrics["correct_steps"]
            / metrics["total_steps"]
        ) * 100
    else:
        accuracy = 0

    # 4. Check whether progress is already saved
    existing_progress = db.query(ProgressHistory).filter(
        ProgressHistory.session_id == session_id
    ).first()

    if existing_progress:
        return existing_progress

    # 5. Create progress record
    progress = ProgressHistory(
        session_id=session_id,
        user_id=session.user_id,
        session_number=session.session_number,
        accuracy=round(accuracy, 2),
        total_mistakes=metrics["total_mistakes"],
        total_attempts=metrics["total_attempts"],
        total_time_seconds=metrics["total_time_seconds"],
        completed_steps=metrics["completed_steps"]
    )

    # 6. Save to database
    db.add(progress)
    db.commit()
    db.refresh(progress)

    return progress