FROM python:3.13-slim AS bit_lib_base

RUN pip install uv

RUN uv init --lib bit_lib
COPY .python-version pyproject.toml uv.lock /bit_lib/
RUN uv --project app sync --no-managed-python
