FROM bit_lib_base:latest AS client_app

# Instalar dependencias del sistema para Tkinter
RUN apt-get update && apt-get install -y \
    python3-tk \
    tk \
    x11-apps \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN uv init --build-backend uv
COPY .python-version pyproject.toml uv.lock ./
COPY src/__init__.py ./src/
COPY src/client/__init__.py ./src/client/
RUN uv sync --no-managed-python

# Puerto P2P
EXPOSE 6881

# Puerto debug
EXPOSE 5678

# Run sync with extras (bit_lib) on container start, then run the app
ENTRYPOINT ["/bin/sh", "-c", "uv sync --extra libs --no-managed-python && exec \"$@\"", "sh"]
CMD ["uv", "run", "python", "src/cli/cli_standalone.py"]
