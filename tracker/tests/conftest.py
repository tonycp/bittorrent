# conftest.py
import pytest
from tracker.containers import Server
from . import base_hdl


@pytest.fixture(scope="session", autouse=True)
def container():
    container = Server()
    container.wire(modules=[base_hdl])
    yield container
    container.shutdown_resources()
