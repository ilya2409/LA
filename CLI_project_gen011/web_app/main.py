import os
import uuid
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from starlette.status import HTTP_413_REQUEST_ENTITY_TOO_LARGE
import ollama
from ollama import Client
from fastapi.staticfiles import StaticFiles

# Импорт slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Импорт нашей анализирующей логики
import sys
sys.path.append(str(Path(__file__).parent.parent))
from analyzer.core import get_all_entries, filter_by_level, filter_by_keyword, filter_by_date_range
from analyzer.models import LogLevel
from analyzer.stats import get_summary, format_summary

app = FastAPI(title="Log Analyzer Web", description="Анализатор логов с ограничением запросов")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Настройка лимитера (хранилище в памяти)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Директории
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Конфигурация безопасности
MAX_FILE_SIZE = 10 * 1024 * 1024          # 10 MB
ALLOWED_EXTENSIONS = {'.log', '.txt'}

def is_safe_filename(filename: str) -> bool:
    """Проверяет, что имя файла не содержит path traversal."""
    return not (".." in filename or "/" in filename or "\\" in filename)

@app.get("/", response_class=HTMLResponse)
async def index():
    # Прямое чтение HTML-файла (без Jinja2, как у тебя работает)
    html_path = Path(__file__).parent / "templates" / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Шаблон не найден. Создайте web_app/templates/index.html</h1>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(html_content)

@app.post("/upload")
@limiter.limit("1/10 seconds")   # 1 запрос в 10 секунд
async def upload_file(request: Request, file: UploadFile = File(...)):
    # Проверка расширения
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Разрешены только .log или .txt файлы")
    
    # Проверка размера
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл превышает {MAX_FILE_SIZE // (1024*1024)} МБ"
        )
    
    # Генерация безопасного имени
    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {"filename": safe_name}

@app.post("/analyze")
@limiter.limit("1/10 seconds")   # 1 запрос в 10 секунд
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    level: Optional[str] = Form(None),
    keyword: Optional[str] = Form(None),
    from_date: Optional[str] = Form(None),
    to_date: Optional[str] = Form(None),
    stats_only: bool = Form(False)
):
    # Безопасность имени файла
    if not is_safe_filename(filename):
        raise HTTPException(400, "Некорректное имя файла")
    
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "Файл не найден")
    
    # Удаляем файл после ответа
    background_tasks.add_task(os.remove, file_path)
    
    try:
        entries = get_all_entries(str(file_path))
    except Exception as e:
        raise HTTPException(500, f"Ошибка чтения файла: {str(e)}")
    
    # Фильтры
    if level:
        try:
            min_level = LogLevel[level.upper()]
            entries = filter_by_level(entries, min_level)
        except KeyError:
            raise HTTPException(400, f"Неизвестный уровень: {level}")
    
    if keyword:
        entries = filter_by_keyword(entries, keyword)
    
    if from_date or to_date:
        from_dt = None
        to_dt = None
        try:
            if from_date:
                from_dt = datetime.strptime(from_date.strip(), "%Y-%m-%d")
            if to_date:
                to_dt = datetime.strptime(to_date.strip(), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Дата должна быть в формате YYYY-MM-DD")
        entries = filter_by_date_range(entries, from_dt, to_dt)
    
    if stats_only:
        summary = get_summary(entries)
        result = format_summary(summary)
    else:
        lines = [f"{e.timestamp} - {e.level.name} - {e.message}" for e in entries]
        result = "\n".join(lines) if lines else "Нет записей по заданным фильтрам."
    
    return {"result": result, "is_stats": stats_only}

# --- ЭНДПОИНТ ДЛЯ AI СВОДКИ ---
@app.post("/ai-summary")
async def ai_summary(
    log_text: str = Form(...),
    model_name: str = Form("gemma4:e2b")
):
    """
    Отправляет текст лога в локальную LLM через Ollama и возвращает краткую сводку.
    """
    if not log_text or len(log_text.strip()) == 0:
        return {"summary": "Нет данных для анализа."}
    
    # Ограничиваем длину текста, чтобы не перегружать модель
    # (примерно 8000 символов — безопасно для 1B модели)
    if len(log_text) > 10000:
        log_text = log_text[:10000] + "\n\n... (лог обрезан для анализа)"
    
    # Промпт для модели
    system_prompt = """Ты — эксперт по анализу логов. Твоя задача — проанализировать предоставленный лог и дать краткую, информативную сводку. В сводке укажи:
1. Основные события, которые произошли.
2. Есть ли критические ошибки или предупреждения.
3. Если есть повторяющиеся ошибки — укажи их частоту.
4. Дай рекомендации: что нужно проверить администратору.

Будь лаконичен (3-5 предложений). Пиши на русском."""
    
    user_prompt = f"""Вот лог для анализа:

{log_text}

Проанализируй его и дай краткую сводку, как описано выше."""
    
    try:
        # Асинхронный вызов Ollama (модель должна быть запущена)
        # Используем синхронный Client в отдельном потоке, чтобы не блокировать FastAPI
        import asyncio
        from functools import partial
        
        def call_ollama():
            client = Client(host='http://localhost:11434')
            response = client.chat(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={
                    "num_ctx": 8192,      # Увеличиваем контекст для больших логов
                    "temperature": 0.3,   # Делаем ответ более детерминированным
                    "top_p": 0.9,
                },
                stream=False
            )
            return response['message']['content']
        
        # Запускаем в потоке, чтобы не блокировать асинхронный цикл
        summary = await asyncio.to_thread(call_ollama)
        return {"summary": summary.strip()}
        
    except ollama._types.ResponseError as e:
        print(f"Ошибка Ollama: {e}")
        return {"summary": f"⚠️ Ошибка при обращении к Ollama: {e.error}. Убедитесь, что модель '{model_name}' установлена и Ollama запущен."}
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        return {"summary": "⚠️ Не удалось получить сводку. Проверьте, запущен ли Ollama."}
