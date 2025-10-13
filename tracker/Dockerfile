FROM python:3.13-slim

RUN pip install uv

COPY .python-version pyproject.toml uv.lock /server/

RUN uv --project server sync --no-managed-python

COPY main.py README.md /server/

CMD ["uv", "--directory", "server", "run", "main.py"]
