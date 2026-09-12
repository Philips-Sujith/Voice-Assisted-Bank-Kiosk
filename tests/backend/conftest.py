"""Shared pytest fixtures."""
import os
import sys
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "services" / "banking-api"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "database"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))


@pytest.fixture(autouse=True)
def reset_queue_manager():
    """Reset the queue manager's daily counter between every test."""
    from app.services.queue_manager import queue_manager
    queue_manager.reset_daily()
    yield
    queue_manager.reset_daily()
