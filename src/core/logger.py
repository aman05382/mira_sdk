"""
Network Automation Framework - Advanced Logging System

Features:
- Colored console output
- Structured JSON logging
- Context propagation (device names, session IDs)
- Log rotation
- Thread-safe operations
- Async queue support for high throughput
"""

import logging
import logging.handlers
import sys
import os
import json
import threading
import queue
import atexit
from datetime import datetime
from typing import Optional, Dict, Any, Union, List
from pathlib import Path
from functools import wraps
import copy

# Try to import colorama for cross-platform colors
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback ANSI codes

    class _Fore:
        BLACK = '\033[30m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        BLUE = '\033[34m'
        MAGENTA = '\033[35m'
        CYAN = '\033[36m'
        WHITE = '\033[37m'
        RESET = '\033[39m'

    class _Style:
        BRIGHT = '\033[1m'
        RESET_ALL = '\033[0m'

    Fore = _Fore()
    Style = _Style()

# Singleton registry
_loggers: Dict[str, 'MiraLogger'] = {}
_lock = threading.Lock()


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""

    # Color mapping
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA + Style.BRIGHT,
    }

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None,
                 use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and (COLORAMA_AVAILABLE or os.name != 'nt')

    def format(self, record: logging.LogRecord) -> str:
        # Make a copy to avoid modifying the original
        record = copy.copy(record)

        if self.use_colors:
            # Add color to levelname
            level_color = self.COLORS.get(record.levelname, Fore.WHITE)
            record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"

            # Add color to message based on level
            if record.levelno >= logging.ERROR:
                record.msg = f"{Fore.RED}{record.msg}{Style.RESET_ALL}"
            elif record.levelno >= logging.WARNING:
                record.msg = f"{Fore.YELLOW}{record.msg}{Style.RESET_ALL}"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, fields: Optional[List[str]] = None,
                 timestamp_format: str = "iso"):
        super().__init__()
        self.fields = fields or [
            'timestamp', 'level', 'logger', 'message',
            'filename', 'lineno', 'function', 'thread',
            'context', 'extra'
        ]
        self.timestamp_format = timestamp_format

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {}

        # Standard fields
        if 'timestamp' in self.fields:
            if self.timestamp_format == "iso":
                log_data['timestamp'] = datetime.fromtimestamp(record.created).isoformat()
            else:
                log_data['timestamp'] = self.formatTime(record)

        if 'level' in self.fields:
            log_data['level'] = record.levelname

        if 'logger' in self.fields:
            log_data['logger'] = record.name

        if 'message' in self.fields:
            log_data['message'] = record.getMessage()

        if 'filename' in self.fields:
            log_data['filename'] = record.filename

        if 'lineno' in self.fields:
            log_data['lineno'] = record.lineno

        if 'function' in self.fields:
            log_data['function'] = record.funcName

        if 'thread' in self.fields:
            log_data['thread_id'] = record.thread
            log_data['thread_name'] = record.threadName

        if 'process' in self.fields:
            log_data['process_id'] = record.process
            log_data['process_name'] = record.processName

        # Exception info
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }

        # Context data (custom attribute)
        if 'context' in self.fields and hasattr(record, 'context'):
            log_data['context'] = record.context

        # Extra fields (custom attributes)
        if 'extra' in self.fields and hasattr(record, 'extra'):
            log_data['extra'] = record.extra

        # Any other attributes
        for key, value in record.__dict__.items():
            if key not in ['timestamp', 'level', 'logger', 'message', 'filename',
                           'lineno', 'function', 'thread', 'threadName', 'process',
                           'processName', 'exc_info', 'exc_text', 'args', 'msg',
                           'created', 'msecs', 'relativeCreated', 'levelno',
                           'levelname', 'pathname', 'module', 'name', 'stack_info']:
                if key not in log_data:
                    log_data[key] = value

        return json.dumps(log_data, default=str)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context information to log records."""

    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        super().__init__(logger, {})
        self.context = context

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message adding context."""
        # Add context to extra
        extra = kwargs.get('extra', {})
        extra['context'] = self.context.copy()
        kwargs['extra'] = extra

        # Also prepend context to message for console readability
        context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
        if context_str:
            msg = f"[{context_str}] {msg}"

        return msg, kwargs

    def add_context(self, **kwargs):
        """Add more context to the adapter."""
        self.context.update(kwargs)
        return self

    def bind(self, **kwargs):
        """Create new adapter with additional context (immutable)."""
        new_context = self.context.copy()
        new_context.update(kwargs)
        return ContextAdapter(self.logger, new_context)


class AsyncHandler(logging.Handler):
    """Asynchronous logging handler using a queue."""

    def __init__(self, handler: logging.Handler, max_queue_size: int = 10000,
                 flush_interval: float = 1.0):
        super().__init__()
        self.handler = handler
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.flush_interval = flush_interval
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._stop_event = threading.Event()
        self._thread.start()
        atexit.register(self.flush)

    def emit(self, record: logging.LogRecord):
        """Put record in queue."""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            # If queue is full, drop oldest or handle error
            self.handleError(record)

    def _process_queue(self):
        """Background thread to process queue."""
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=self.flush_interval)
                if record is not None:
                    self.handler.emit(record)
            except queue.Empty:
                continue
            except Exception:
                self.handleError(record)

    def flush(self):
        """Flush remaining records."""
        self._stop_event.set()
        # Process remaining items
        while not self.queue.empty():
            try:
                record = self.queue.get_nowait()
                self.handler.emit(record)
            except queue.Empty:
                break
            except Exception:
                pass
        self.handler.flush()

    def close(self):
        """Close handler."""
        self.flush()
        self.handler.close()
        super().close()


class MiraLogger:
    """
    Advanced logger wrapper with context management and multiple output formats.

    This is the main class users interact with.
    """

    # Default format strings
    DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    SIMPLE_FORMAT = "%(levelname)s: %(message)s"

    def __init__(self, name: str, level: int = logging.INFO):
        self.name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._handlers: List[logging.Handler] = []
        self._context: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # Remove existing handlers to avoid duplicates
        self._logger.handlers = []

    def add_console_handler(
        self,
        level: int = logging.INFO,
        fmt: Optional[str] = None,
        use_colors: bool = True,
        stream=sys.stdout
    ):
        """Add console handler with optional colors."""
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)

        if use_colors:
            formatter = ColoredFormatter(
                fmt or self.DEFAULT_FORMAT,
                datefmt="%Y-%m-%d %H:%M:%S",
                use_colors=True
            )
        else:
            formatter = logging.Formatter(
                fmt or self.DEFAULT_FORMAT,
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        handler.setFormatter(formatter)

        with self._lock:
            self._logger.addHandler(handler)
            self._handlers.append(handler)

        return self

    def add_file_handler(
        self,
        filepath: Union[str, Path],
        level: int = logging.DEBUG,
        fmt: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        encoding: str = 'utf-8'
    ):
        """Add rotating file handler."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            filepath,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding
        )
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt or self.DETAILED_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        with self._lock:
            self._logger.addHandler(handler)
            self._handlers.append(handler)

        return self

    def add_json_file_handler(
        self,
        filepath: Union[str, Path],
        level: int = logging.DEBUG,
        fields: Optional[List[str]] = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5
    ):
        """Add JSON rotating file handler for structured logging."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            filepath,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.setLevel(level)
        formatter = JSONFormatter(fields=fields)
        handler.setFormatter(formatter)

        with self._lock:
            self._logger.addHandler(handler)
            self._handlers.append(handler)

        return self

    def add_async_handler(self, handler: logging.Handler, max_queue_size: int = 10000):
        """Wrap an existing handler with async processing."""
        async_handler = AsyncHandler(handler, max_queue_size)

        with self._lock:
            self._logger.addHandler(async_handler)
            self._handlers.append(async_handler)

        return self

    def set_context(self, **kwargs):
        """Set global context for all log messages."""
        self._context.update(kwargs)
        return self

    def clear_context(self):
        """Clear global context."""
        self._context.clear()
        return self

    def bind(self, **kwargs) -> ContextAdapter:
        """Create a context-bound logger adapter."""
        context = self._context.copy()
        context.update(kwargs)
        return ContextAdapter(self._logger, context)

    def _log(self, level: int, msg: str, *args, **kwargs):
        """Internal log method with context handling."""
        extra = kwargs.get('extra', {})

        # Merge global context
        if self._context:
            context = extra.get('context', {})
            merged_context = self._context.copy()
            merged_context.update(context)
            extra['context'] = merged_context
            kwargs['extra'] = extra

        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log a debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log an info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log a warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log an error message."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log a critical message."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args, exc_info=True, **kwargs):
        """Log an exception message."""
        self._log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def log(self, level: int, msg: str, *args, **kwargs):
        """Log a message with a specific level."""
        self._log(level, msg, *args, **kwargs)

    def banner(self, msg: str, level: int = logging.INFO, width: int = 80, char: str = '='):
        """Log a banner message."""
        top = char * width
        bottom = char * width
        empty_line = char + ' ' * (width - 2) + char
        msg_line = char + f"{msg}".center(width - 2) + char
        self._log(level, top)
        self._log(level, empty_line)
        self._log(level, msg_line)
        self._log(level, empty_line)
        self._log(level, bottom)

    def success(self, msg: str, *args, **kwargs):
        """Log a success message (INFO level with green color)."""
        if COLORAMA_AVAILABLE:
            msg = f"{Fore.GREEN}{msg}{Style.RESET_ALL}"
        self._log(logging.INFO, msg, *args, **kwargs)

    def set_level(self, level: Union[int, str]):
        """Set logging level."""
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        self._logger.setLevel(level)
        for handler in self._handlers:
            handler.setLevel(level)
        return self

    def flush(self):
        """Flush all handlers."""
        for handler in self._handlers:
            handler.flush()

    def close(self):
        """Close all handlers."""
        for handler in self._handlers:
            handler.close()
        self._handlers.clear()


def get_logger(
    name: Optional[str] = None,
    level: Union[int, str] = logging.INFO,
    console: bool = True,
    log_file: Optional[Union[str, Path]] = None,
    json_file: Optional[Union[str, Path]] = None,
    context: Optional[Dict[str, Any]] = None
) -> MiraLogger:
    """
    Get or create a logger instance.

    This is the main entry point for logging in the framework.

    Args:
        name: Logger name (default: caller's module name)
        level: Logging level
        console: Enable console output
        log_file: Path to text log file
        json_file: Path to JSON structured log file
        context: Initial context dictionary

    Returns:
        Logger instance

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting connection")

        >>> # With context
        >>> logger = get_logger("sonic", context={"device": "leaf1"})
        >>> logger.info("Connected")  # [device=leaf1] Connected

        >>> # Bind new context
        >>> conn_logger = logger.bind(session_id="abc123")
        >>> conn_logger.info("Command sent")  # [device=leaf1, session_id=abc123] Command sent
    """
    global _loggers

    if name is None:
        # Get caller's module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')

    with _lock:
        if name in _loggers:
            logger = _loggers[name]
        else:
            logger = MiraLogger(name, level=level if isinstance(level, int) else getattr(logging, level.upper()))
            _loggers[name] = logger

            # Setup default handlers if new logger
            if console:
                logger.add_console_handler()

            if log_file:
                logger.add_file_handler(log_file)

            if json_file:
                logger.add_json_file_handler(json_file)

            if context:
                logger.set_context(**context)

    return logger


# Decorator for logging function entry/exit
def log_execution(logger_name: Optional[str] = None, level: int = logging.DEBUG):
    """Decorator to log function entry and exit."""
    def decorator(func):
        logger = get_logger(logger_name or func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__
            logger.log(level, f"ENTER: {func_name}")
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"EXIT: {func_name} - SUCCESS")
                return result
            except Exception as e:
                logger.error(f"EXIT: {func_name} - FAILED: {e}")
                raise

        return wrapper
    return decorator


# Performance monitoring context manager
class Timer:
    """Context manager to time and log operations."""

    def __init__(self, logger: MiraLogger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.log(self.level, f"START: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        if exc_type:
            self.logger.error(f"FAILED: {self.operation} after {duration:.3f}s - {exc_val}")
        else:
            self.logger.log(self.level, f"COMPLETE: {self.operation} in {duration:.3f}s")

        return False

    @property
    def elapsed(self):
        """
        Get elapsed time in seconds.
        """
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
