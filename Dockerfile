FROM python:3.12-slim
RUN useradd -m -u 1000 rotxt && mkdir /data && chown rotxt:rotxt /data
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
    "pydantic-settings>=2.6" "passlib>=1.7.4" "bcrypt==4.0.1"
WORKDIR /app
COPY server ./server
COPY shared ./shared
COPY data ./data
COPY web ./web
USER rotxt
ENV ROTXT_DB_PATH=/data/rotxt.db ROTXT_SERVER_HOST=0.0.0.0 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
