from sqlalchemy.orm import Session

from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.services.performance_service import calculate_session_metrics


def compare_training_sessions(
    user_id: int,
    session_1_number: int,
    session_2_number: int,
    db: Session
):

    session_1 = db.query(TrainingSession).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_number == session_1_number,
        TrainingSession.session_type == "TRAINING"
    ).order_by(
        TrainingSession.start_time.desc()
    ).first()

    session_2 = db.query(TrainingSession).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.session_number == session_2_number,
        TrainingSession.session_type == "TRAINING"
    ).order_by(
        TrainingSession.start_time.desc()
    ).first()

    # 3. Validate sessions
    if not session_1:
        return None

    if not session_2:
        return None

    # 4. Calculate metrics for both sessions
    metrics_1 = calculate_session_metrics(
        session_1.id,
        db
    )

    metrics_2 = calculate_session_metrics(
        session_2.id,
        db
    )

    # 5. Calculate accuracy
    accuracy_1 = (
        metrics_1["correct_steps"]
        / metrics_1["total_steps"]
    ) * 100 if metrics_1["total_steps"] > 0 else 0

    accuracy_2 = (
        metrics_2["correct_steps"]
        / metrics_2["total_steps"]
    ) * 100 if metrics_2["total_steps"] > 0 else 0

    # 6. Calculate changes
    accuracy_change = accuracy_2 - accuracy_1

    mistakes_change = (
        metrics_2["total_mistakes"]
        - metrics_1["total_mistakes"]
    )

    attempts_change = (
        metrics_2["total_attempts"]
        - metrics_1["total_attempts"]
    )

    time_change = (
        metrics_2["total_time_seconds"]
        - metrics_1["total_time_seconds"]
    )

    # 7. Determine overall improvement
    if accuracy_change > 0 and mistakes_change <= 0:
        overall_result = "IMPROVED"

    elif accuracy_change < 0 or mistakes_change > 0:
        overall_result = "DECLINED"

    else:
        overall_result = "NO_SIGNIFICANT_CHANGE"

    # 8. Compare step-level performance
    step_comparison = []

    steps_1 = db.query(StepPerformance).filter(
        StepPerformance.session_id == session_1.id
    ).all()

    steps_2 = db.query(StepPerformance).filter(
        StepPerformance.session_id == session_2.id
    ).all()

    steps_1_dict = {
        step.step_id: step
        for step in steps_1
    }

    steps_2_dict = {
        step.step_id: step
        for step in steps_2
    }

    # Compare all 16 clinical steps
    for step_id in range(16):

        step_1 = steps_1_dict.get(step_id)
        step_2 = steps_2_dict.get(step_id)

        mistakes_1 = step_1.mistakes if step_1 else 0
        mistakes_2 = step_2.mistakes if step_2 else 0

        attempts_1 = step_1.attempts if step_1 else 0
        attempts_2 = step_2.attempts if step_2 else 0

        if mistakes_2 < mistakes_1:
            step_result = "IMPROVED"

        elif mistakes_2 > mistakes_1:
            step_result = "DECLINED"

        else:
            step_result = "NO_CHANGE"

        step_comparison.append({
            "step_id": step_id,
            "step_name": (
                step_2.step_name
                if step_2
                else step_1.step_name
                if step_1
                else None
            ),
            "training_1_attempts": attempts_1,
            "training_1_mistakes": mistakes_1,
            "training_2_attempts": attempts_2,
            "training_2_mistakes": mistakes_2,
            "mistake_change": mistakes_2 - mistakes_1,
            "result": step_result
        })

    # 9. Return comparison
    return {
        "user_id": user_id,

        "training_1": {
            "session_id": session_1.id,
            "session_number": session_1.session_number,
            "accuracy": round(accuracy_1, 2),
            "mistakes": metrics_1["total_mistakes"],
            "attempts": metrics_1["total_attempts"],
            "time_seconds": metrics_1["total_time_seconds"],
            "completed_steps": metrics_1["completed_steps"]
        },

        "training_2": {
            "session_id": session_2.id,
            "session_number": session_2.session_number,
            "accuracy": round(accuracy_2, 2),
            "mistakes": metrics_2["total_mistakes"],
            "attempts": metrics_2["total_attempts"],
            "time_seconds": metrics_2["total_time_seconds"],
            "completed_steps": metrics_2["completed_steps"]
        },

        "changes": {
            "accuracy_change": round(accuracy_change, 2),
            "mistakes_change": mistakes_change,
            "attempts_change": attempts_change,
            "time_change_seconds": round(time_change, 2)
        },

        "overall_result": overall_result,

        "step_comparison": step_comparison
    }