FROM bit_lib_base:latest AS tracker_app

WORKDIR /app

RUN uv init --build-backend uv
COPY .python-version pyproject.toml uv.lock ./
COPY src/__init__.py ./src
RUN uv sync --no-managed-python

# Run sync with extras (bit_lib) on container start, then run the app
ENTRYPOINT ["/bin/sh", "-c", "uv sync --extra libs --no-managed-python && uv run app"]
