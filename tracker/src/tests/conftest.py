# conftest.py
import pytest
from src.containers import AppContainer
from . import base_hdl


@pytest.fixture(scope="session", autouse=True)
def container():
    container = AppContainer()
    container.wire(modules=[base_hdl])
    yield container
    container.shutdown_resources()
