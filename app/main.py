from fastapi import FastAPI

from app.database.database import Base, engine
from app.database.models import (
    User,
    TrainingSession,
    StepPerformance,
    Mistake,
    WeakArea,
    ProgressHistory,
    GuidanceProfile, TrainingReport, CumulativeWeakArea, TestReport, GuidanceStep
)

from app.api.users import router as users_router
from app.api.sessions import router as sessions_router
from app.api.step_performance import router as step_performance_router
from app.api.mistakes import router as mistakes_router
from app.api.performance import router as performance_router
from app.api.weak_areas import router as weak_area_router
from app.api.progress import router as progress_router
from app.api.comparison import router as comparison_router
from app.api.guidance import router as guidance_router
from app.api.training_report import router as training_report_router
from app.api.test_assessment import router as test_assessment_router
from app.api.cumulative_weak_area import router as cumulative_weak_area_router
from app.api.test_report import router as test_report_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Medical VR Training Backend",
    version="1.0.0"
)

app.include_router(users_router)
app.include_router(sessions_router)
app.include_router(step_performance_router)
app.include_router(mistakes_router)
app.include_router(performance_router)
app.include_router(weak_area_router)
app.include_router(progress_router)
app.include_router(comparison_router)
app.include_router(guidance_router)
app.include_router(training_report_router)
app.include_router(test_assessment_router)
app.include_router(cumulative_weak_area_router)
app.include_router(test_report_router)
app.include_router(dashboard_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "Medical VR Training Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }