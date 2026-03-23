# Stage 1: Builder - установка зависимостей
FROM python:3.12-alpine AS builder

WORKDIR /app

# Установим build-зависимости
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# Копируем pyproject.toml и poetry.lock
COPY pyproject.toml poetry.lock* ./

# Устанавливаем poetry и зависимости в виртуальное окружение
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create true && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-root

# Stage 2: Runtime - финальный образ
FROM python:3.12-alpine

WORKDIR /app

# Установим Doppler CLI
RUN wget -q -t3 'https://packages.doppler.com/public/cli/rsa.8004D9FF50437357.key' -O /etc/apk/keys/cli@doppler-8004D9FF50437357.rsa.pub && \
    echo 'https://packages.doppler.com/public/cli/alpine/any-version/main' | tee -a /etc/apk/repositories && \
    apk add doppler

# Копируем виртуальное окружение из builder
COPY --from=builder /app/.venv /app/.venv

# Копируем исходный код приложения
COPY src/ ./src/
COPY pyproject.toml ./

# Переменные окружения по умолчанию для сервера
ENV PYTHONUNBUFFERED=1
ENV HOST=localhost
ENV PORT=8080
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8080

# Запуск сервера через Doppler для управления переменными окружения
CMD ["doppler", "run", "--", "python", "-m", "main"]
