from sqlalchemy.orm import Session

from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.training_report import TrainingReport
from app.database.models.test_report import TestReport
from app.database.models.progress_history import ProgressHistory
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.database.models.guidance_profile import GuidanceProfile
from app.database.models.guidance_step import GuidanceStep

from app.services.performance_service import calculate_session_metrics


def get_dashboard(user_id: int, db: Session):

    # ---------------------------------------------------------
    # 1. Get user
    # ---------------------------------------------------------
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        return None

    # ---------------------------------------------------------
    # 2. Latest Training Session
    #    Select by actual session creation/start time.
    #    Do NOT depend on status or end_time.
    # ---------------------------------------------------------
    latest_training = db.query(
        TrainingSession
    ).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_type == "TRAINING"
    ).order_by(
        TrainingSession.start_time.desc()
    ).first()

    # ---------------------------------------------------------
    # 3. Latest Test Session
    # ---------------------------------------------------------
    latest_test = db.query(
        TrainingSession
    ).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_type == "TEST"
    ).order_by(
        TrainingSession.start_time.desc()
    ).first()

    # ---------------------------------------------------------
    # 4. Latest Training Metrics
    # ---------------------------------------------------------
    training_summary = None

    if latest_training:

        metrics = calculate_session_metrics(
            latest_training.id,
            db
        )

        if metrics:

            # Try to get an existing training report
            training_report = db.query(
                TrainingReport
            ).filter(
                TrainingReport.session_id == latest_training.id
            ).first()

            training_summary = {
                "session_id": latest_training.id,
                "session_number": latest_training.session_number,
                "total_steps": metrics["total_steps"],
                "completed_steps": metrics["completed_steps"],
                "correct_steps": metrics["correct_steps"],
                "accuracy": round(
                    (
                        metrics["correct_steps"]
                        / metrics["total_steps"]
                        * 100
                    )
                    if metrics["total_steps"] > 0
                    else 0,
                    2
                ),
                "total_attempts": metrics["total_attempts"],
                "total_mistakes": metrics["total_mistakes"],
                "first_attempt_correct_count":
                    metrics.get(
                        "first_attempt_correct_count",
                        0
                    ),
                "first_attempt_accuracy":
                    metrics.get(
                        "first_attempt_accuracy",
                        0
                    ),
                "total_time_seconds":
                    metrics["total_time_seconds"],
                "average_step_time_seconds":
                    metrics.get(
                        "average_step_time_seconds",
                        0
                    ),
                "overall_result":
                    training_report.overall_result
                    if training_report
                    else (
                        "COMPLETED"
                        if metrics["completed_steps"] == 16
                        else "NEEDS_PRACTICE"
                    )
            }

    # ---------------------------------------------------------
    # 5. Latest Test Summary
    # ---------------------------------------------------------
    test_summary = None

    if latest_test:

        metrics = calculate_session_metrics(
            latest_test.id,
            db
        )

        if metrics:

            test_report = db.query(
                TestReport
            ).filter(
                TestReport.session_id == latest_test.id
            ).first()

            test_summary = {
                "session_id": latest_test.id,
                "session_number": latest_test.session_number,
                "total_steps": metrics["total_steps"],
                "completed_steps": metrics["completed_steps"],
                "correct_steps": metrics["correct_steps"],
                "accuracy": round(
                    (
                        metrics["correct_steps"]
                        / metrics["total_steps"]
                        * 100
                    )
                    if metrics["total_steps"] > 0
                    else 0,
                    2
                ),
                "total_attempts": metrics["total_attempts"],
                "total_mistakes": metrics["total_mistakes"],
                "first_attempt_correct_count":
                    metrics.get(
                        "first_attempt_correct_count",
                        0
                    ),
                "first_attempt_accuracy":
                    metrics.get(
                        "first_attempt_accuracy",
                        0
                    ),
                "total_time_seconds":
                    metrics["total_time_seconds"],
                "average_step_time_seconds":
                    metrics.get(
                        "average_step_time_seconds",
                        0
                    ),
                "result":
                    test_report.result
                    if test_report
                    else "NOT_ASSESSED"
            }

    # ---------------------------------------------------------
    # 6. Progress History
    # ---------------------------------------------------------
    progress = db.query(
        ProgressHistory
    ).filter(
        ProgressHistory.user_id == user_id
    ).order_by(
        ProgressHistory.session_number.asc(),
        ProgressHistory.id.asc()
    ).all()

    progress_data = []

    for item in progress:
        progress_data.append({
            "session_id": item.session_id,
            "session_number": item.session_number,
            "accuracy": item.accuracy,
            "total_mistakes": item.total_mistakes,
            "total_attempts": item.total_attempts,
            "total_time_seconds": item.total_time_seconds,
            "completed_steps": item.completed_steps
        })

    # ---------------------------------------------------------
    # 7. Cumulative Weak Areas
    # ---------------------------------------------------------
    weak_areas = db.query(
        CumulativeWeakArea
    ).filter(
        CumulativeWeakArea.user_id == user_id
    ).order_by(
        CumulativeWeakArea.rank.asc()
    ).all()

    weak_area_data = []

    for area in weak_areas:
        weak_area_data.append({
            "step_id": area.step_id,
            "step_name": area.step_name,
            "total_attempts": area.total_attempts,
            "total_mistakes": area.total_mistakes,
            "mistake_ratio": area.mistake_ratio,
            "severity": area.severity,
            "rank": area.rank,
            "last_session_id": area.last_session_id
        })

    # ---------------------------------------------------------
    # 8. Latest Adaptive Guidance
    # ---------------------------------------------------------
    latest_guidance_profile = db.query(
        GuidanceProfile
    ).filter(
        GuidanceProfile.user_id == user_id
    ).order_by(
        GuidanceProfile.profile_version.desc()
    ).first()

    guidance_data = []

    if latest_guidance_profile:

        guidance_steps = db.query(
            GuidanceStep
        ).filter(
            GuidanceStep.guidance_profile_id ==
            latest_guidance_profile.id
        ).order_by(
            GuidanceStep.step_id.asc()
        ).all()

        for step in guidance_steps:
            guidance_data.append({
                "step_id": step.step_id,
                "step_name": step.step_name,
                "guidance_level": step.guidance_level,
                "mistake_count": step.mistake_count,
                "mistake_ratio": step.mistake_ratio,
                "guidance_message": step.guidance_message
            })

    # ---------------------------------------------------------
    # 9. Dashboard Response
    # ---------------------------------------------------------
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        },

        "latest_training": training_summary,

        "latest_test": test_summary,

        "progress": progress_data,

        "cumulative_weak_areas": weak_area_data,

        "adaptive_guidance": {
            "guidance_available":
                latest_guidance_profile is not None,

            "profile_id":
                latest_guidance_profile.id
                if latest_guidance_profile
                else None,

            "profile_version":
                latest_guidance_profile.profile_version
                if latest_guidance_profile
                else None,

            "session_target":
                latest_guidance_profile.session_target
                if latest_guidance_profile
                else None,

            "guidance": guidance_data
        }
    }