FROM python:3.14-alpine AS builder

ENV POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apk add --no-cache build-base libffi-dev openssl-dev \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml ./
RUN poetry export --without-hashes --format requirements.txt --output requirements.txt

FROM python:3.14-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser -D botuser

COPY --from=builder /app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app/src

USER botuser

WORKDIR /app/src

CMD ["python", "-m", "main"]
