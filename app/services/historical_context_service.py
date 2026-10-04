from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.models.session import TrainingSession
from app.database.models.progress_history import ProgressHistory
from app.database.models.mistake import Mistake
from app.database.models.step_performance import StepPerformance
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.config.constants import STEPS


def get_user_historical_context(
    user_id: int,
    current_session_id: int,
    db: Session
) -> Dict[str, Any]:
    """
    Retrieve user-isolated historical training/testing context.
    
    Security Guarantee:
    - All queries are strictly filtered by user_id.
    - Only completed sessions prior to current_session_id are included.
    - No cross-user data leakage.
    - Compact payload to avoid LLM token bloat.
    """
    # 1. Fetch current session to determine cutoff
    current_session = db.query(TrainingSession).filter(
        TrainingSession.id == current_session_id,
        TrainingSession.user_id == user_id
    ).first()

    cutoff_time = current_session.start_time if current_session else None

    # 2. Query previous completed sessions strictly for this user
    query = db.query(TrainingSession).filter(
        TrainingSession.user_id == user_id,
        TrainingSession.id != current_session_id,
        TrainingSession.status == "COMPLETED"
    )
    if cutoff_time:
        query = query.filter(TrainingSession.start_time <= cutoff_time)
    
    prior_sessions = query.order_by(TrainingSession.start_time.asc()).all()
    prior_session_ids = [s.id for s in prior_sessions]

    total_prior_sessions = len(prior_sessions)

    if total_prior_sessions == 0:
        return {
            "previous_sessions": 0,
            "total_previous_sessions": 0,
            "previous_accuracy": [],
            "previous_accuracy_trend": [],
            "previous_results": [],
            "average_historical_accuracy": None,
            "recurring_weak_areas": [],
            "prior_session_summary": "First recorded session for this trainee. No prior history exists."
        }

    # 3. Retrieve accuracy trend and results from reports/progress
    progress_records = db.query(ProgressHistory).filter(
        ProgressHistory.user_id == user_id,
        ProgressHistory.session_id.in_(prior_session_ids)
    ).order_by(ProgressHistory.created_at.asc()).all()

    accuracy_trend: List[float] = []
    if progress_records:
        accuracy_trend = [round(p.accuracy, 2) for p in progress_records]
    else:
        for s_id in prior_session_ids:
            correct_cnt = db.query(func.count(StepPerformance.id)).filter(
                StepPerformance.session_id == s_id,
                StepPerformance.completed == True,
                StepPerformance.mistakes == 0
            ).scalar() or 0
            accuracy_trend.append(round((correct_cnt / 16.0) * 100.0, 2))

    avg_accuracy = (
        round(sum(accuracy_trend) / len(accuracy_trend), 2)
        if accuracy_trend else None
    )

    # Prior results (PASS, FAIL, SATISFACTORY, etc.)
    previous_results: List[str] = []
    for s in prior_sessions:
        if s.session_type == "TEST":
            t_rep = db.query(TestReport).filter(TestReport.session_id == s.id).first()
            if t_rep:
                previous_results.append(t_rep.result)
        else:
            tr_rep = db.query(TrainingReport).filter(TrainingReport.session_id == s.id).first()
            if tr_rep:
                previous_results.append(tr_rep.overall_result)

    # 4. Identify recurring weak areas across prior sessions
    step_mistake_sessions = db.query(
        Mistake.step_id,
        func.count(func.distinct(Mistake.session_id)).label("session_count"),
        func.count(Mistake.id).label("total_mistake_count")
    ).filter(
        Mistake.session_id.in_(prior_session_ids)
    ).group_by(Mistake.step_id).order_by(
        func.count(func.distinct(Mistake.session_id)).desc()
    ).all()

    recurring_weak_areas: List[Dict[str, Any]] = []
    for step_id, sess_cnt, tot_mistakes in step_mistake_sessions:
        if sess_cnt >= 1:
            step_name = STEPS.get(step_id, f"Step {step_id}")
            if sess_cnt >= 3 or tot_mistakes >= 4:
                sev = "HIGH"
            elif sess_cnt >= 2 or tot_mistakes >= 2:
                sev = "MEDIUM"
            else:
                sev = "LOW"

            recurring_weak_areas.append({
                "step_id": step_id,
                "step_name": step_name,
                "occurrences": sess_cnt,
                "prior_sessions_with_mistakes": sess_cnt,
                "total_prior_mistakes": tot_mistakes,
                "historical_severity": sev
            })

    recurring_weak_areas = recurring_weak_areas[:5]

    return {
        "previous_sessions": total_prior_sessions,
        "total_previous_sessions": total_prior_sessions,
        "previous_accuracy": accuracy_trend,
        "previous_accuracy_trend": accuracy_trend,
        "previous_results": previous_results,
        "average_historical_accuracy": avg_accuracy,
        "recurring_weak_areas": recurring_weak_areas,
        "prior_session_summary": (
            f"Trainee completed {total_prior_sessions} prior session(s) with an "
            f"average historical accuracy of {avg_accuracy}%."
        )
    }
