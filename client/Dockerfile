FROM python:3.13-slim

RUN apt-get update && apt-get install -y python3-tk tk

RUN pip install uv

COPY .python-version pyproject.toml uv.lock /app/

RUN uv --project app sync --no-managed-python

COPY main.py README.md /app/

RUN pip install debugpy
EXPOSE 5678

CMD ["uv", "--directory", "app", "run", "main.py"]
