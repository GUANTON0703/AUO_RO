FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN uv pip install --system --no-cache \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
    "pydantic-settings>=2.6" "passlib>=1.7.4" "bcrypt==4.0.1"

FROM python:3.12-slim
RUN useradd -m -u 1000 rotxt && mkdir /data && chown rotxt:rotxt /data
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/uvicorn /usr/local/bin/uvicorn
WORKDIR /app
COPY server ./server
COPY shared ./shared
COPY data ./data
COPY web ./web
USER rotxt
ENV ROTXT_DB_PATH=/data/rotxt.db ROTXT_SERVER_HOST=0.0.0.0 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
