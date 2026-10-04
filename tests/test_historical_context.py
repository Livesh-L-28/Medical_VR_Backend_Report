import pytest
from datetime import datetime, timedelta

from app.database.models.session import TrainingSession
from app.database.models.progress_history import ProgressHistory
from app.database.models.mistake import Mistake
from app.database.models.step_performance import StepPerformance
from app.services.historical_context_service import get_user_historical_context
from app.config.constants import STEPS


def test_first_session_has_empty_historical_context(db_session, test_user_1):
    session = TrainingSession(
        session_id="s1",
        user_id=test_user_1.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )
    db_session.add(session)
    db_session.commit()

    context = get_user_historical_context(
        user_id=test_user_1.id,
        current_session_id=session.id,
        db=db_session
    )
    assert context["total_previous_sessions"] == 0
    assert context["previous_accuracy_trend"] == []
    assert context["average_historical_accuracy"] is None
    assert context["recurring_weak_areas"] == []


def test_historical_context_user_isolation(db_session, test_user_1, test_user_2):
    """Ensure User 1's completed sessions are NEVER returned in User 2's context."""
    # User 1 completes 2 sessions
    t1 = datetime.utcnow() - timedelta(hours=2)
    s1_u1 = TrainingSession(
        session_id="u1-s1",
        user_id=test_user_1.id,
        session_type="TRAINING",
        session_number=1,
        start_time=t1,
        end_time=t1 + timedelta(minutes=5),
        status="COMPLETED"
    )
    db_session.add(s1_u1)
    db_session.commit()

    p1 = ProgressHistory(
        session_id=s1_u1.id,
        user_id=test_user_1.id,
        session_number=1,
        accuracy=75.0,
        total_mistakes=2,
        total_attempts=18,
        total_time_seconds=120.0,
        completed_steps=16
    )
    db_session.add(p1)

    # User 1 mistake on Step 3
    m1 = Mistake(
        session_id=s1_u1.id,
        step_id=3,
        mistake_type="WRONG_OBJECT",
        attempt_number=1
    )
    db_session.add(m1)
    db_session.commit()

    # User 2 starts a new session
    s1_u2 = TrainingSession(
        session_id="u2-s1",
        user_id=test_user_2.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )
    db_session.add(s1_u2)
    db_session.commit()

    # Query context for User 2
    u2_context = get_user_historical_context(
        user_id=test_user_2.id,
        current_session_id=s1_u2.id,
        db=db_session
    )

    # User 2 must see ZERO prior sessions and NO weak areas from User 1
    assert u2_context["total_previous_sessions"] == 0
    assert u2_context["previous_accuracy_trend"] == []
    assert u2_context["recurring_weak_areas"] == []

    # Query context for User 1's next session
    s2_u1 = TrainingSession(
        session_id="u1-s2",
        user_id=test_user_1.id,
        session_type="TRAINING",
        session_number=2,
        start_time=datetime.utcnow(),
        status="IN_PROGRESS"
    )
    db_session.add(s2_u1)
    db_session.commit()

    u1_context = get_user_historical_context(
        user_id=test_user_1.id,
        current_session_id=s2_u1.id,
        db=db_session
    )
    assert u1_context["total_previous_sessions"] == 1
    assert u1_context["previous_accuracy_trend"] == [75.0]
    assert u1_context["average_historical_accuracy"] == 75.0
    assert len(u1_context["recurring_weak_areas"]) == 1
    assert u1_context["recurring_weak_areas"][0]["step_id"] == 3
