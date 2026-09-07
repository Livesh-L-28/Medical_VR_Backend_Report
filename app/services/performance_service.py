from sqlalchemy.orm import Session

from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake


TOTAL_STEPS = 16


def calculate_session_metrics(
    session_id: int,
    db: Session
):
    # Check session
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        return None

    # Get all step performance records
    step_records = db.query(StepPerformance).filter(
        StepPerformance.session_id == session_id
    ).all()

    # Get all mistakes
    mistake_records = db.query(Mistake).filter(
        Mistake.session_id == session_id
    ).all()

    # Total completed steps
    completed_steps = sum(
        1 for step in step_records
        if step.completed
    )

    # Correct steps
    correct_steps = sum(
        1 for step in step_records
        if step.completed and step.mistakes == 0
    )

    # Total attempts
    total_attempts = sum(
        step.attempts for step in step_records
    )

    # Total mistakes
    total_mistakes = sum(
        step.mistakes for step in step_records
    )

    # First-attempt correct steps
    first_attempt_correct_count = sum(
        1
        for step in step_records
        if step.first_attempt_correct
    )

    # First attempt accuracy
    if completed_steps > 0:
        first_attempt_accuracy = (
            first_attempt_correct_count
            / completed_steps
        ) * 100
    else:
        first_attempt_accuracy = 0

    # Total time
    total_time = sum(
        step.step_time_seconds
        for step in step_records
    )

    # Average step time
    if completed_steps > 0:
        average_step_time = (
            total_time / completed_steps
        )
    else:
        average_step_time = 0

    # Mistakes by step
    mistakes_by_step = {}

    for mistake in mistake_records:
        step_id = mistake.step_id

        if step_id not in mistakes_by_step:
            mistakes_by_step[step_id] = 0

        mistakes_by_step[step_id] += 1

    # Mistakes by type
    mistakes_by_type = {}

    for mistake in mistake_records:
        mistake_type = mistake.mistake_type

        if mistake_type not in mistakes_by_type:
            mistakes_by_type[mistake_type] = 0

        mistakes_by_type[mistake_type] += 1

    return {
        "session_id": session_id,
        "session_type": session.session_type,
        "session_number": session.session_number,

        "total_steps": TOTAL_STEPS,
        "completed_steps": completed_steps,
        "correct_steps": correct_steps,

        "total_attempts": total_attempts,
        "total_mistakes": total_mistakes,

        "first_attempt_correct_count":
            first_attempt_correct_count,

        "first_attempt_accuracy":
            round(first_attempt_accuracy, 2),

        "total_time_seconds":
            round(total_time, 2),

        "average_step_time_seconds":
            round(average_step_time, 2),

        "mistakes_by_step":
            mistakes_by_step,

        "mistakes_by_type":
            mistakes_by_type
    }