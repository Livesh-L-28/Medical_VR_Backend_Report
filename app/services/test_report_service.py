from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.test_report import TestReport
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.services.test_assessment_service import assess_test_session

from app.services.cumulative_weak_area_service import (
    calculate_cumulative_weak_areas
)


def generate_test_report(session_id: int, db: Session):

    # ---------------------------------------------------------
    # 1. Validate TEST session
    # ---------------------------------------------------------
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Test session not found"
        )

    if session.session_type != "TEST":
        raise HTTPException(
            status_code=400,
            detail="Test report can only be generated for TEST sessions"
        )

    # ---------------------------------------------------------
    # 2. Validate user
    # ---------------------------------------------------------
    user = db.query(User).filter(
        User.id == session.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # ---------------------------------------------------------
    # 3. Generate deterministic assessment
    # ---------------------------------------------------------
    assessment = assess_test_session(
        session_id=session_id,
        db=db
    )

    # ---------------------------------------------------------
    # 4. Get step performance
    # ---------------------------------------------------------
    step_performances = db.query(
        StepPerformance
    ).filter(
        StepPerformance.session_id == session_id
    ).order_by(
        StepPerformance.step_id.asc()
    ).all()

    # ---------------------------------------------------------
    # 5. Get mistake details
    # ---------------------------------------------------------
    mistakes = db.query(
        Mistake
    ).filter(
        Mistake.session_id == session_id
    ).order_by(
        Mistake.step_id.asc(),
        Mistake.attempt_number.asc()
    ).all()

    # ---------------------------------------------------------
    # 6. Recalculate cumulative weak areas
    #
    # Includes ALL Training + Test mistakes and attempts.
    # This updates the cumulative weak score before the
    # Test Report reads the weak areas.
    # ---------------------------------------------------------
    calculate_cumulative_weak_areas(
        user_id=session.user_id,
        db=db
    )

    # Get the UPDATED cumulative weak areas
    weak_areas = db.query(
        CumulativeWeakArea
    ).filter(
        CumulativeWeakArea.user_id == session.user_id
    ).order_by(
        CumulativeWeakArea.rank.asc()
    ).all()
    # ---------------------------------------------------------
    # 7. Check whether report already exists
    # ---------------------------------------------------------
    existing_report = db.query(
        TestReport
    ).filter(
        TestReport.session_id == session_id
    ).first()

    if existing_report:
        report = existing_report
    else:

        # -----------------------------------------------------
        # 8. Create Test Report
        # -----------------------------------------------------
        report = TestReport(
            session_id=session.id,
            user_id=session.user_id,
            session_number=session.session_number,

            total_steps=assessment["total_steps"],
            completed_steps=assessment["completed_steps"],
            correct_steps=assessment["correct_steps"],
            accuracy=assessment["accuracy"],

            total_attempts=assessment["total_attempts"],
            total_mistakes=assessment["total_mistakes"],

            first_attempt_correct_count=(
                assessment["first_attempt_correct_count"]
            ),

            first_attempt_accuracy=(
                assessment["first_attempt_accuracy"]
            ),

            total_time_seconds=(
                assessment["total_time_seconds"]
            ),

            average_step_time_seconds=(
                assessment["average_step_time_seconds"]
            ),

            result=assessment["result"]
        )

        db.add(report)
        db.commit()
        db.refresh(report)

    # ---------------------------------------------------------
    # 9. Prepare detailed step performance
    # ---------------------------------------------------------
    step_details = []

    for step in step_performances:

        step_details.append({
            "step_id": step.step_id,
            "step_name": step.step_name,
            "attempts": step.attempts,
            "mistakes": step.mistakes,
            "first_attempt_correct": (
                step.first_attempt_correct
            ),
            "step_time_seconds": (
                step.step_time_seconds
            ),
            "completed": step.completed
        })

    # ---------------------------------------------------------
    # 10. Prepare mistake details
    # ---------------------------------------------------------
    mistake_details = []

    for mistake in mistakes:

        mistake_details.append({
            "step_id": mistake.step_id,
            "mistake_type": mistake.mistake_type,
            "attempt_number": mistake.attempt_number,
            "timestamp": mistake.timestamp
        })

    # ---------------------------------------------------------
    # 11. Prepare weak-area details
    #
    # Only include weak areas that actually have mistakes.
    # ---------------------------------------------------------
    weak_area_details = []

    for area in weak_areas:

        if area.total_mistakes > 0:

            weak_area_details.append({
                "step_id": area.step_id,
                "step_name": area.step_name,
                "total_attempts": area.total_attempts,
                "total_mistakes": area.total_mistakes,
                "mistake_ratio": area.mistake_ratio,
                "severity": area.severity,
                "rank": area.rank
            })

    # ---------------------------------------------------------
    # 12. Return complete Test Report
    # ---------------------------------------------------------
    return {
        "report": {
            "id": report.id,
            "session_id": report.session_id,
            "user_id": report.user_id,
            "session_number": report.session_number,

            "total_steps": report.total_steps,
            "completed_steps": report.completed_steps,
            "correct_steps": report.correct_steps,
            "accuracy": report.accuracy,

            "total_attempts": report.total_attempts,
            "total_mistakes": report.total_mistakes,

            "first_attempt_correct_count": (
                report.first_attempt_correct_count
            ),

            "first_attempt_accuracy": (
                report.first_attempt_accuracy
            ),

            "total_time_seconds": (
                report.total_time_seconds
            ),

            "average_step_time_seconds": (
                report.average_step_time_seconds
            ),

            "result": report.result
        },

        "step_performance": step_details,

        "mistakes": mistake_details,

        "weak_areas": weak_area_details
    }