"""
Модели данных для анализатора логов.
Определяет структуру записи лога и перечисление уровней логирования.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """
    Уровни логирования в порядке возрастания важности.
    Значения чисел позволяют сравнивать уровни (DEBUG < INFO < ...).
    """
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def from_string(cls, name: str) -> 'LogLevel':
        """Преобразует строку (например, 'ERROR') в элемент Enum."""
        return cls[name.upper()]

    def __str__(self) -> str:
        return self.name


@dataclass
class LogEntry:
    """
    Одна структурированная запись из лог-файла.
    
    Attributes:
        timestamp: Дата и время события.
        level: Уровень логирования (DEBUG, INFO, ...).
        message: Текст сообщения.
        source: Необязательный источник (модуль, функция, IP и т.д.).
    """
    timestamp: datetime
    level: LogLevel
    message: str
    source: Optional[str] = None

    def __repr__(self) -> str:
        return (f"LogEntry(timestamp={self.timestamp!r}, "
                f"level={self.level.name}, "
                f"message={self.message[:50]!r})")