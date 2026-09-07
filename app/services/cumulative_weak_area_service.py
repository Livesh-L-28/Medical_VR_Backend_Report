from sqlalchemy.orm import Session

from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.config.constants import STEPS


def calculate_cumulative_weak_areas(user_id: int, db: Session):

    # Get all TRAINING and TEST sessions for this user
    sessions = db.query(TrainingSession).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_type.in_(["TRAINING", "TEST"])
    ).all()

    # Remove old cumulative analysis
    db.query(CumulativeWeakArea).filter(
        CumulativeWeakArea.user_id == user_id
    ).delete()

    cumulative_data = {}

    # Process every session
    for session in sessions:

        step_performances = db.query(StepPerformance).filter(
            StepPerformance.session_id == session.id
        ).all()

        mistakes = db.query(Mistake).filter(
            Mistake.session_id == session.id
        ).all()

        # Add attempts from StepPerformance
        for step in step_performances:

            if step.step_id not in cumulative_data:
                cumulative_data[step.step_id] = {
                    "attempts": 0,
                    "mistakes": 0,
                    "last_session_id": session.id
                }

            cumulative_data[step.step_id]["attempts"] += step.attempts

            cumulative_data[step.step_id]["last_session_id"] = session.id

        # Add mistakes from Mistake records
        for mistake in mistakes:

            if mistake.step_id not in cumulative_data:
                cumulative_data[mistake.step_id] = {
                    "attempts": 0,
                    "mistakes": 0,
                    "last_session_id": session.id
                }

            cumulative_data[mistake.step_id]["mistakes"] += 1

            cumulative_data[mistake.step_id]["last_session_id"] = session.id

    # Create cumulative weak-area records
    weak_areas = []

    for step_id, data in cumulative_data.items():

        attempts = data["attempts"]
        mistakes = data["mistakes"]

        if attempts > 0:
            mistake_ratio = (mistakes / attempts) * 100
        else:
            mistake_ratio = 0

        if mistake_ratio >= 50:
            severity = "HIGH"
        elif mistake_ratio >= 25:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        weak_areas.append({
            "step_id": step_id,
            "step_name": STEPS[step_id],
            "attempts": attempts,
            "mistakes": mistakes,
            "mistake_ratio": mistake_ratio,
            "severity": severity,
            "last_session_id": data["last_session_id"]
        })

    # Rank weak areas
    weak_areas.sort(
        key=lambda x: (
            -x["mistakes"],
            -x["mistake_ratio"]
        )
    )

    # Save ranking
    for rank, area in enumerate(weak_areas, start=1):

        cumulative_area = CumulativeWeakArea(
            user_id=user_id,
            step_id=area["step_id"],
            step_name=area["step_name"],
            total_attempts=area["attempts"],
            total_mistakes=area["mistakes"],
            mistake_ratio=round(area["mistake_ratio"], 2),
            severity=area["severity"],
            rank=rank,
            last_session_id=area["last_session_id"]
        )

        db.add(cumulative_area)

    db.commit()

    return db.query(CumulativeWeakArea).filter(
        CumulativeWeakArea.user_id == user_id
    ).order_by(
        CumulativeWeakArea.rank.asc()
    ).all()