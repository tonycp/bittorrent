FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY uv.lock pyproject.toml /app/

RUN uv sync

COPY . /app/

CMD ["python", "app.py"]
