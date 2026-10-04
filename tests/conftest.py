import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.database import Base, get_db
from app.main import app as fastapi_app
import app.database.models  # Register all models on Base.metadata
from app.database.models.user import User
from app.database.models.session import TrainingSession
from app.database.models.step_performance import StepPerformance
from app.database.models.mistake import Mistake
from app.database.models.weak_area import WeakArea
from app.database.models.progress_history import ProgressHistory
from app.database.models.cumulative_weak_area import CumulativeWeakArea
from app.database.models.test_report import TestReport
from app.database.models.training_report import TrainingReport
from app.database.models.ai_feedback import AIReportFeedback
from app.utils.security import hash_password, create_access_token
from app.config.constants import STEPS

from sqlalchemy.pool import StaticPool

# In-memory SQLite for fast, isolated test execution
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database schema for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def test_user_1(db_session):
    user = User(
        name="Trainee One",
        email="trainee1@example.com",
        password_hash=hash_password("Password123!")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_2(db_session):
    user = User(
        name="Trainee Two",
        email="trainee2@example.com",
        password_hash=hash_password("Password123!")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user_1(test_user_1):
    token = create_access_token(user_id=test_user_1.id, email=test_user_1.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_2(test_user_2):
    token = create_access_token(user_id=test_user_2.id, email=test_user_2.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def completed_test_session_pass(db_session, test_user_1):
    """Create a 16/16 completed TEST session with 0 mistakes (PASS)."""
    session = TrainingSession(
        session_id="session-pass-1",
        user_id=test_user_1.id,
        session_type="TEST",
        session_number=1,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=120.0,
        status="COMPLETED"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # 16 correct completed steps
    for step_id in range(16):
        sp = StepPerformance(
            session_id=session.id,
            step_id=step_id,
            step_name=STEPS[step_id],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=7.5,
            completed=True
        )
        db_session.add(sp)
    db_session.commit()
    return session


@pytest.fixture
def completed_test_session_fail(db_session, test_user_1):
    """Create a TEST session with 1 mistake on Step 7 (FAIL)."""
    session = TrainingSession(
        session_id="session-fail-1",
        user_id=test_user_1.id,
        session_type="TEST",
        session_number=2,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=150.0,
        status="COMPLETED"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    for step_id in range(16):
        mistake_cnt = 1 if step_id == 7 else 0
        sp = StepPerformance(
            session_id=session.id,
            step_id=step_id,
            step_name=STEPS[step_id],
            attempts=2 if step_id == 7 else 1,
            mistakes=mistake_cnt,
            first_attempt_correct=False if step_id == 7 else True,
            step_time_seconds=9.0,
            completed=True
        )
        db_session.add(sp)

    mistake = Mistake(
        session_id=session.id,
        step_id=7,
        mistake_type="WRONG_OBJECT",
        attempt_number=1
    )
    db_session.add(mistake)

    wa = WeakArea(
        session_id=session.id,
        step_id=7,
        step_name=STEPS[7],
        attempts=2,
        mistakes=1,
        mistake_ratio=50.0,
        severity="HIGH",
        rank=1
    )
    db_session.add(wa)

    db_session.commit()
    return session


@pytest.fixture
def completed_training_session(db_session, test_user_1):
    """Create a 16/16 completed TRAINING session with 0 mistakes (EXCELLENT)."""
    session = TrainingSession(
        session_id="session-train-1",
        user_id=test_user_1.id,
        session_type="TRAINING",
        session_number=1,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        total_time_seconds=140.0,
        status="COMPLETED"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    for step_id in range(16):
        sp = StepPerformance(
            session_id=session.id,
            step_id=step_id,
            step_name=STEPS[step_id],
            attempts=1,
            mistakes=0,
            first_attempt_correct=True,
            step_time_seconds=8.0,
            completed=True
        )
        db_session.add(sp)
    db_session.commit()
    return session

