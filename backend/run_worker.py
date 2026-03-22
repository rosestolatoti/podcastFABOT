#!/usr/bin/env python3
import asyncio
import logging
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from arq import run_worker
from backend.workers.podcast_worker import WorkerSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Iniciando Worker ARQ...")
    run_worker(WorkerSettings)
