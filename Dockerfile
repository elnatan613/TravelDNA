# Build the React application once, then serve it from the FastAPI process.
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /build/frontend
RUN npm ci
COPY frontend/ ./
# Questionnaire.jsx imports ../../data/experience_cards.json. Keep the same
# directory relationship that Vite has in the source checkout.
COPY data/experience_cards.json /build/data/experience_cards.json
RUN npm run build


FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRAVELDNA_RAG_MODE=lexical

COPY requirements.production.txt ./
RUN pip install --no-cache-dir -r requirements.production.txt

COPY . ./
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# Railway supplies PORT at runtime; 8000 keeps the container usable locally.
CMD ["sh", "-c", "python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
