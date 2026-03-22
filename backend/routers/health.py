import logging
import os
import shutil
from pathlib import Path

import aiohttp
from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthStatus(BaseModel):
    service: str
    status: str
    details: str | None = None


@router.get("/")
async def health_check():
    results = []

    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        results.append(HealthStatus(service="redis", status="UP", details=None))
    except Exception as e:
        results.append(HealthStatus(service="redis", status="DOWN", details=str(e)))

    try:
        disk = shutil.disk_usage("/")
        free_gb = disk.free / (1024**3)
        if free_gb < 0.5:
            results.append(
                HealthStatus(
                    service="disk",
                    status="WARNING",
                    details=f"Apenas {free_gb:.1f}GB livres",
                )
            )
        else:
            results.append(
                HealthStatus(
                    service="disk", status="UP", details=f"{free_gb:.1f}GB livres"
                )
            )
    except Exception as e:
        results.append(HealthStatus(service="disk", status="UNKNOWN", details=str(e)))

    if settings.OLLAMA_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{settings.OLLAMA_URL}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    ollama_status = "UP" if resp.status == 200 else "DOWN"
                    results.append(
                        HealthStatus(
                            service="ollama",
                            status=ollama_status,
                            details=f"Status: {resp.status}",
                        )
                    )
        except Exception as e:
            results.append(
                HealthStatus(service="ollama", status="DOWN", details=str(e))
            )

    try:
        import subprocess

        result = subprocess.run(
            ["pgrep", "-f", "run_worker.py"], capture_output=True, text=True
        )
        worker_alive = result.returncode == 0

        if worker_alive:
            results.append(HealthStatus(service="worker", status="UP", details=None))
        else:
            results.append(
                HealthStatus(
                    service="worker",
                    status="DOWN",
                    details="Worker não está rodando",
                )
            )
    except Exception as e:
        results.append(HealthStatus(service="worker", status="DOWN", details=str(e)))

    overall = (
        "healthy"
        if all(r.status in ["UP", "WARNING"] for r in results)
        else "unhealthy"
    )

    return {"overall": overall, "services": [r.model_dump() for r in results]}
