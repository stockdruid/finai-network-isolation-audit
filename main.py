from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import (
    auth,
    chat,
    controls,
    detectors,
    diagnosis,
    health,
    isms_p,
    logs,
    pii_risk,
    policies,
    reports,
    requirements,
    stats,
    users,
)
from middlewares.logging import setup_structlog
from middlewares.request_id import RequestIdMiddleware
from middlewares.timing import TimingMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_structlog()
    yield


app = FastAPI(
    title="금융 AI 망분리 컴플라이언스 진단",
    version="0.1.0",
    description="VPC A 내부망 시뮬레이션 + 진단 엔진 폴링 API",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(TimingMiddleware)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(auth.router, tags=["auth"])
app.include_router(users.router, tags=["users"])
app.include_router(logs.router, tags=["logs"])
app.include_router(diagnosis.router, tags=["diagnosis"])
app.include_router(policies.router, tags=["policies"])
app.include_router(controls.router, tags=["controls"])
app.include_router(detectors.router, tags=["detectors"])
app.include_router(requirements.router, tags=["requirements"])
app.include_router(pii_risk.router, tags=["pii-risk"])
app.include_router(isms_p.router, tags=["isms-p"])
app.include_router(stats.router, tags=["stats"])
app.include_router(reports.router, tags=["reports"])
