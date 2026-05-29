# ---- Этап 1: Билдер для установки зависимостей ----
FROM python:3.12-slim AS builder

# Устанавливаем системные зависимости для компиляции (если нужны)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Этап 2: Финальный образ ----
FROM python:3.12-slim

# Создаём непривилегированного пользователя для запуска приложения
RUN addgroup --system app && adduser --system --group app

# Копируем установленные пакеты из этапа-билдера
COPY --from=builder /root/.local /home/app/.local

# Копируем весь код приложения
COPY --chown=app:app . /app

# Устанавливаем переменную окружения PATH для pip --user
ENV PATH=/home/app/.local/bin:$PATH

# Устанавливаем рабочую директорию
WORKDIR /app

# Переключаемся на непривилегированного пользователя
USER app

# Открываем порт, который слушает приложение (8000)
EXPOSE 8000

# Команда для запуска сервера (gunicorn с uvicorn воркерами)
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "web_app.main:app"]