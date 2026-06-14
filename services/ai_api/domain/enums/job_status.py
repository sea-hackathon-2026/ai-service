"""Job status enum - Tracks the lifecycle state of an AI processing job."""

from enum import StrEnum


class JobStatus(StrEnum):
    """Possible states of an AI processing job."""

    PENDING = "pending"  # Job created, waiting in queue
    PROCESSING = "processing"  # Model is loading / warming up
    STREAMING = "streaming"  # Actively generating and streaming chunks
    DONE = "done"  # Successfully completed
    FAILED = "failed"  # Failed with error
    CANCELLED = "cancelled"  # Cancelled by user
