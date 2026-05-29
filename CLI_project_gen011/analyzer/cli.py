"""
Модуль командной строки.
Обрабатывает аргументы, управляет фильтрацией и выводом.
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from .models import LogLevel, LogEntry
from .core import stream_logs, filter_by_level, filter_by_keyword, filter_by_date_range
from .stats import get_summary, format_summary


def parse_date(date_str: str) -> datetime:
    """
    Преобразует строку в объект datetime.
    Поддерживает форматы: YYYY-MM-DD и YYYY-MM-DD HH:MM:SS.
    
    Args:
        date_str: Строка с датой/временем.
    
    Returns:
        Объект datetime.
    
    Raises:
        argparse.ArgumentTypeError: если формат неверный.
    """
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Неверный формат даты: '{date_str}'. Используйте YYYY-MM-DD или YYYY-MM-DD HH:MM:SS"
    )


def create_parser() -> argparse.ArgumentParser:
    """Создаёт и возвращает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="log-analyzer",
        description="CLI-анализатор логов. Фильтрация, поиск ошибок, сводка по событиям.",
        epilog="Пример: python main.py app.log --level ERROR --stats"
    )
    
    # Позиционный аргумент: путь к лог-файлу
    parser.add_argument(
        "logfile",
        help="Путь к лог-файлу для анализа"
    )
    
    # Фильтр по уровню
    parser.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Минимальный уровень логирования (показывать только этот уровень и выше)"
    )
    
    # Поиск по ключевому слову
    parser.add_argument(
        "--search",
        type=str,
        help="Ключевое слово для поиска в сообщениях (регистронезависимо)"
    )
    
    # Фильтр по дате
    parser.add_argument(
        "--from",
        dest="from_date",
        type=parse_date,
        metavar="DATETIME",
        help="Начало временного диапазона (YYYY-MM-DD или YYYY-MM-DD HH:MM:SS)"
    )
    
    parser.add_argument(
        "--to",
        dest="to_date",
        type=parse_date,
        metavar="DATETIME",
        help="Конец временного диапазона (YYYY-MM-DD или YYYY-MM-DD HH:MM:SS)"
    )
    
    # Режим сводки
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Показать сводную статистику вместо списка записей"
    )
    
    # Сохранение в файл
    parser.add_argument(
        "--output",
        type=str,
        help="Сохранить результат в указанный файл (по умолчанию вывод в консоль)"
    )
    
    return parser


def run(args: argparse.Namespace) -> None:
    """
    Запускает анализ на основе переданных аргументов.
    
    Args:
        args: Распарсенные аргументы от create_parser().
    """
    # 1. Читаем логи потоково, но для фильтрации и статистики нужен список
    #    (для больших файлов можно оптимизировать, но пока так)
    entries: List[LogEntry] = list(stream_logs(args.logfile))
    
    if not entries:
        print("Не найдено ни одной корректной записи в лог-файле.", file=sys.stderr)
        sys.exit(1)
    
    # 2. Применяем фильтры (цепочка)
    filtered = entries
    
    if args.level:
        min_level = LogLevel[args.level]
        filtered = filter_by_level(filtered, min_level)
    
    if args.search:
        filtered = filter_by_keyword(filtered, args.search)
    
    if args.from_date or args.to_date:
        filtered = filter_by_date_range(filtered, args.from_date, args.to_date)
    
    # 3. Формируем вывод
    if args.stats:
        summary = get_summary(filtered)
        output_text = format_summary(summary)
    else:
        # Выводим каждую запись в формате "timestamp - LEVEL - message"
        lines = []
        for e in filtered:
            lines.append(f"{e.timestamp} - {e.level.name} - {e.message}")
        output_text = "\n".join(lines) if lines else "Нет записей, соответствующих фильтрам."
    
    # 4. Сохраняем или печатаем
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Результат сохранён в файл: {args.output}")
    else:
        print(output_text)


def main() -> None:
    """Точка входа для CLI (вызывается из main.py)."""
    parser = create_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    # Для прямого запуска python -m analyzer.cli (удобно при отладке)
    main()