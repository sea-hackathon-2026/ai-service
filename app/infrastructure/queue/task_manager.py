"""
Task Manager - Manages background AI processing tasks.

Uses asyncio tasks for lightweight background processing.
Can be extended to use Celery for distributed task execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Manages background asyncio tasks for AI processing.

    Tracks running tasks by job_id, supports cancellation,
    and provides status queries.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}

    def submit(
        self,
        job_id: str,
        coro: Coroutine[Any, Any, Any],
    ) -> asyncio.Task:
        """
        Submit a coroutine as a background task.

        Args:
            job_id: Unique identifier to track this task.
            coro: The coroutine to execute in the background.

        Returns:
            The asyncio.Task object.
        """
        task = asyncio.create_task(coro, name=f"job-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda t: self._cleanup(job_id))
        logger.info("Background task submitted: %s", job_id)
        return task

    def cancel(self, job_id: str) -> bool:
        """Cancel a running background task."""
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            logger.info("Task cancelled: %s", job_id)
            return True
        return False

    def is_running(self, job_id: str) -> bool:
        """Check if a task is currently running."""
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    def get_active_count(self) -> int:
        """Return the number of active tasks."""
        return sum(1 for t in self._tasks.values() if not t.done())

    def _cleanup(self, job_id: str) -> None:
        """Remove completed tasks from tracking."""
        self._tasks.pop(job_id, None)

    async def shutdown(self) -> None:
        """Cancel all running tasks during shutdown."""
        for job_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                logger.info("Shutting down task: %s", job_id)
        # Wait for all tasks to finish
        if self._tasks:
            await asyncio.gather(
                *self._tasks.values(), return_exceptions=True
            )
        self._tasks.clear()
