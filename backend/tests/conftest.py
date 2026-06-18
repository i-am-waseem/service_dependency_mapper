"""
Shared test fixtures.

Resets all module-level state between every test so tests are fully
isolated regardless of execution order.
"""
import pytest
from app.services import graph_service
from app.routers.analysis import reset_jobs


@pytest.fixture(autouse=True)
def reset_state():
    """
    Runs before and after every test automatically (autouse=True).
    Clears the in-memory graph and job store so no test inherits
    state from a previous test.
    """
    graph_service.reset()
    reset_jobs()
    yield
    graph_service.reset()
    reset_jobs()
