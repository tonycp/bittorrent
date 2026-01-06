FROM bit_lib_base:latest AS tracker_app

WORKDIR /app

RUN uv init --build-backend uv
COPY .python-version pyproject.toml uv.lock /
RUN uv sync --no-managed-python

ENTRYPOINT ["uv", "sync", "--extra", "libs", "--no-managed-python"]
CMD ["uv", "run", "app"]
