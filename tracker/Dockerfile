FROM python:3.13-slim

RUN pip install uv

COPY .python-version pyproject.toml uv.lock /app/

RUN uv --project app sync --no-managed-python

COPY main.py README.md /app/

CMD ["uv", "--directory", "app", "run", "main.py"]
