from sqlalchemy.orm import Session

from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.weak_area import WeakArea


def determine_severity(mistake_ratio: float) -> str:
    if mistake_ratio >= 50:
        return "HIGH"
    elif mistake_ratio >= 25:
        return "MEDIUM"
    else:
        return "LOW"


def analyze_weak_areas(session_id: int, db: Session):

    # 1. Check whether session exists
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        return None

    # 2. Get step performance records
    step_records = db.query(StepPerformance).filter(
        StepPerformance.session_id == session_id
    ).all()

    # 3. Get mistake records
    mistake_records = db.query(Mistake).filter(
        Mistake.session_id == session_id
    ).all()

    # 4. Count mistakes for each step
    mistake_counts = {}

    for mistake in mistake_records:

        if mistake.step_id not in mistake_counts:
            mistake_counts[mistake.step_id] = 0

        mistake_counts[mistake.step_id] += 1

    # 5. Calculate weak areas
    weak_areas = []

    for step in step_records:

        mistakes = mistake_counts.get(step.step_id, 0)

        # Ignore steps with no mistakes
        if mistakes == 0:
            continue

        attempts = step.attempts

        if attempts > 0:
            mistake_ratio = (mistakes / attempts) * 100
        else:
            mistake_ratio = 0

        severity = determine_severity(mistake_ratio)

        weak_areas.append({
            "session_id": session_id,
            "step_id": step.step_id,
            "step_name": step.step_name,
            "attempts": attempts,
            "mistakes": mistakes,
            "mistake_ratio": round(mistake_ratio, 2),
            "severity": severity
        })

    # 6. Rank weak areas
    weak_areas.sort(
        key=lambda x: (x["mistakes"], x["mistake_ratio"]),
        reverse=True
    )

    for index, area in enumerate(weak_areas, start=1):
        area["rank"] = index

    # 7. Remove old analysis for this session only
    db.query(WeakArea).filter(
        WeakArea.session_id == session_id
    ).delete(synchronize_session=False)

    # 8. Save new weak-area results
    for area in weak_areas:

        weak_area = WeakArea(
            session_id=area["session_id"],
            step_id=area["step_id"],
            step_name=area["step_name"],
            attempts=area["attempts"],
            mistakes=area["mistakes"],
            mistake_ratio=area["mistake_ratio"],
            severity=area["severity"],
            rank=area["rank"]
        )

        db.add(weak_area)

    # 9. Commit to PostgreSQL
    db.commit()

    # 10. Return calculated results
    return weak_areas