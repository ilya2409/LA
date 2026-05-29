"""
Основная логика анализатора логов.
Содержит парсинг строк, фильтрацию по уровню, ключевому слову и дате.
"""

import re
from datetime import datetime
from typing import List, Generator, Optional

from .models import LogEntry, LogLevel


# Компилируем регулярное выражение для стандартного формата Python logging:
# "2025-05-28 12:34:56,789 - ERROR - Сообщение"
LOG_PATTERN = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+'
    r'(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+-\s+'
    r'(?P<message>.*)'
)


def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Парсит одну строку лога в структурированный объект LogEntry.
    
    Args:
        line: Строка из лог-файла.
    
    Returns:
        LogEntry, если парсинг успешен, иначе None (пропускаем некорректные строки).
    """
    line = line.strip()
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    # Парсим timestamp
    ts_str = match.group('timestamp')
    try:
        # Формат: YYYY-MM-DD HH:MM:SS,fff
        timestamp = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S,%f')
    except ValueError:
        return None

    # Получаем уровень логирования
    level_name = match.group('level')
    try:
        level = LogLevel[level_name]
    except KeyError:
        return None

    message = match.group('message')
    return LogEntry(timestamp=timestamp, level=level, message=message)


def stream_logs(file_path: str) -> Generator[LogEntry, None, None]:
    """
    Генератор для потокового чтения логов из файла.
    Не загружает весь файл в память, что позволяет обрабатывать большие файлы.
    
    Args:
        file_path: Путь к лог-файлу.
    
    Yields:
        LogEntry для каждой корректной строки.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                yield entry


def filter_by_level(entries: List[LogEntry], min_level: LogLevel) -> List[LogEntry]:
    """
    Фильтрует записи, оставляя только те, чей уровень не ниже min_level.
    
    Args:
        entries: Список записей логов.
        min_level: Минимальный уровень (включительно).
    
    Returns:
        Отфильтрованный список.
    """
    return [e for e in entries if e.level.value >= min_level.value]


def filter_by_keyword(entries: List[LogEntry], keyword: str) -> List[LogEntry]:
    """
    Фильтрует записи, оставляя только те, в сообщении которых содержится keyword.
    
    Args:
        entries: Список записей логов.
        keyword: Ключевое слово для поиска (регистронезависимо).
    
    Returns:
        Отфильтрованный список.
    """
    kw_lower = keyword.lower()
    return [e for e in entries if kw_lower in e.message.lower()]


def filter_by_date_range(
    entries: List[LogEntry], 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None
) -> List[LogEntry]:
    """
    Фильтрует записи по временному диапазону.
    
    Args:
        entries: Список записей логов.
        start_date: Начало диапазона (включительно). Если None - без нижней границы.
        end_date: Конец диапазона (включительно). Если None - без верхней границы.
    
    Returns:
        Отфильтрованный список.
    """
    result = entries
    if start_date:
        result = [e for e in result if e.timestamp >= start_date]
    if end_date:
        result = [e for e in result if e.timestamp <= end_date]
    return result


def get_all_entries(file_path: str) -> List[LogEntry]:
    """
    Загружает все записи из лог-файла в список (для небольших файлов).
    Для больших файлов предпочтительнее использовать stream_logs.
    
    Args:
        file_path: Путь к лог-файлу.
    
    Returns:
        Список всех корректных LogEntry.
    """
    return list(stream_logs(file_path))