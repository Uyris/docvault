"""Observability endpoint feeding the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.metrics import MetricsResponse
from app.services.analytics import compute_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(session: AsyncSession = Depends(get_session)) -> MetricsResponse:
    data = await compute_metrics(session)
    return MetricsResponse(**data)
