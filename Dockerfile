# ---- frontend build (static SPA, served by FastAPI from /srv/web-dist) ----
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- backend runtime ----
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY mission_control ./mission_control
COPY --from=web /web/dist /srv/web-dist

RUN mkdir -p /srv/data
ENV DATA_DIR=/srv/data
ENV FRONTEND_DIST=/srv/web-dist

EXPOSE 8000
CMD ["uvicorn", "mission_control.main:app", "--host", "0.0.0.0", "--port", "8000"]
