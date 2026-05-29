"""
Модуль статистики.
Подсчитывает распределение по уровням логирования, топ сообщений и временной диапазон.
"""

from collections import Counter
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from .models import LogEntry, LogLevel


def count_by_level(entries: List[LogEntry]) -> Dict[LogLevel, int]:
    """
    Подсчитывает количество записей по каждому уровню логирования.
    
    Args:
        entries: Список записей логов.
    
    Returns:
        Словарь {уровень: количество} (включая уровни с нулевым значением).
    """
    counts = {level: 0 for level in LogLevel}
    for entry in entries:
        counts[entry.level] += 1
    return counts


def get_top_messages(entries: List[LogEntry], top_n: int = 3) -> List[Tuple[str, int]]:
    """
    Возвращает топ-N самых частых сообщений.
    
    Args:
        entries: Список записей логов.
        top_n: Количество самых частых сообщений.
    
    Returns:
        Список кортежей (сообщение, количество), отсортированный по убыванию частоты.
    """
    message_counter = Counter(entry.message for entry in entries)
    return message_counter.most_common(top_n)


def get_time_range(entries: List[LogEntry]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Возвращает минимальную и максимальную временную метку в логах.
    
    Args:
        entries: Список записей логов.
    
    Returns:
        Кортеж (start, end) или (None, None) если список пуст.
    """
    if not entries:
        return None, None
    
    start = min(entry.timestamp for entry in entries)
    end = max(entry.timestamp for entry in entries)
    return start, end


def get_summary(entries: List[LogEntry]) -> Dict:
    """
    Формирует полную сводку по логам в виде словаря.
    
    Args:
        entries: Список записей логов.
    
    Returns:
        Словарь со следующими ключами:
            - total: общее количество записей
            - by_level: словарь {имя_уровня: количество}
            - top_messages: список (сообщение, количество)
            - time_range: кортеж (начало, конец)
    """
    if not entries:
        return {
            'total': 0,
            'by_level': {level.name: 0 for level in LogLevel},
            'top_messages': [],
            'time_range': (None, None)
        }
    
    level_counts = count_by_level(entries)
    top_msgs = get_top_messages(entries, top_n=3)
    start, end = get_time_range(entries)
    
    return {
        'total': len(entries),
        'by_level': {level.name: count for level, count in level_counts.items() if count > 0},
        'top_messages': top_msgs,
        'time_range': (start, end)
    }


def format_summary(summary: Dict) -> str:
    """
    Форматирует словарь статистики в удобочитаемую строку.
    
    Args:
        summary: Словарь от get_summary().
    
    Returns:
        Строка с отформатированной сводкой.
    """
    lines = []
    lines.append("=== СВОДКА ПО СОБЫТИЯМ ===")
    lines.append(f"Всего записей: {summary['total']}")
    
    lines.append("\nПо уровням:")
    for level, count in summary['by_level'].items():
        lines.append(f"  {level}: {count}")
    
    if summary['top_messages']:
        lines.append("\nТоп сообщений:")
        for msg, count in summary['top_messages']:
            # Ограничиваем длину сообщения для читаемости
            msg_preview = msg[:100] + "..." if len(msg) > 100 else msg
            lines.append(f"  [{count}] {msg_preview}")
    
    start, end = summary['time_range']
    if start and end:
        lines.append(f"\nВременной диапазон:")
        lines.append(f"  start: {start}")
        lines.append(f"  end:   {end}")
    else:
        lines.append("\nНет записей для анализа.")
    
    return "\n".join(lines)