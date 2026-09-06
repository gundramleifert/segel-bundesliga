"""Background jobs in the FastAPI process — without Redis, without workers.

Intentionally kept small: a job registry in memory, work runs as an asyncio task.
This carries exactly the load it's meant for — an event organizer occasionally computing
a pairing list.

**The cost, stated openly:** Jobs live only as long as the server process. A restart
mid-optimization loses it, and with multiple uvicorn workers each would only see its own jobs.
As long as the server runs as a single process, this is properly dimensioned; once that
changes, state belongs in the database — then this file is where that happens.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# This many completed jobs are kept so the registry doesn't grow unbounded.
MAX_FINISHED_JOBS = 50


class JobStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    kind: str
    status: str = JobStatus.RUNNING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def finished(self) -> bool:
        return self.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)

    def report(self, progress: float, message: str = "") -> None:
        """Called by the running job to report progress."""
        self.progress = max(0.0, min(1.0, progress))
        if message:
            self.message = message


class JobRegistry:
    def __init__(self, max_finished: int = MAX_FINISHED_JOBS) -> None:
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._max_finished = max_finished

    def start(self, kind: str, work: Callable[[Job], Awaitable[Any]]) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job, work), name=f"job:{kind}:{job.id}")
        return job

    async def _run(self, job: Job, work: Callable[[Job], Awaitable[Any]]) -> None:
        try:
            job.result = await work(job)
            job.status = JobStatus.DONE
            job.progress = 1.0
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.error = "The job was cancelled."
            raise
        except Exception as exc:  # noqa: BLE001 — the job must not bring down the server
            job.status = JobStatus.FAILED
            job.error = str(exc)
            logger.exception("Job %s (%s) failed", job.id, job.kind)
        finally:
            job.finished_at = datetime.now(UTC)
            self._trim()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.finished or job.task is None:
            return False
        job.task.cancel()
        return True

    def list(self, kind: str | None = None) -> list[Job]:
        jobs = list(self._jobs.values())
        if kind is not None:
            jobs = [job for job in jobs if job.kind == kind]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def _trim(self) -> None:
        finished = [job_id for job_id, job in self._jobs.items() if job.finished]
        for job_id in finished[: max(0, len(finished) - self._max_finished)]:
            del self._jobs[job_id]

    async def shutdown(self) -> None:
        """Cancel running jobs cleanly on shutdown instead of cutting them off silently."""
        running = [job for job in self._jobs.values() if not job.finished and job.task]
        for job in running:
            job.task.cancel()  # type: ignore[union-attr]
        for job in running:
            try:
                await job.task  # type: ignore[arg-type]
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


jobs = JobRegistry()
