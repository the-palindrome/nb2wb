from __future__ import annotations

from contextlib import contextmanager
import logging
import sys
from typing import Iterator

_PACKAGE_LOGGER_NAME = "nb2wb"
_DEFAULT_HANDLER_NAME = "nb2wb.default.stderr"


def configure_logging(*, verbose: bool = False) -> logging.Logger:
    """Configure package logging for interactive use.

    Args:
        verbose: Whether to enable package debug logging.

    Returns:
        The package logger.
    """
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if not verbose:
        return logger

    logger.setLevel(logging.DEBUG)
    if not logger.hasHandlers():
        handler = _build_default_handler()
        logger.addHandler(handler)
        logger.propagate = False
    return logger


@contextmanager
def verbose_logging(enabled: bool) -> Iterator[logging.Logger]:
    """Temporarily enable package debug logging for one operation.

    Args:
        enabled: Whether verbose logging should be enabled in this scope.

    Returns:
        A context manager yielding the package logger.
    """
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if not enabled:
        yield logger
        return

    previous_level = logger.level
    previous_propagate = logger.propagate
    added_handler = False

    logger.setLevel(logging.DEBUG)
    if not logger.hasHandlers():
        logger.addHandler(_build_default_handler())
        logger.propagate = False
        added_handler = True

    try:
        yield logger
    finally:
        logger.setLevel(previous_level)
        if added_handler:
            _remove_default_handlers(logger)
            logger.propagate = previous_propagate


def _build_default_handler() -> logging.Handler:
    """Create the default stderr handler used for verbose package logs."""
    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(_DEFAULT_HANDLER_NAME)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    return handler


def _remove_default_handlers(logger: logging.Logger) -> None:
    """Remove the default verbose stderr handler from a logger."""
    for handler in list(logger.handlers):
        if handler.get_name() == _DEFAULT_HANDLER_NAME:
            logger.removeHandler(handler)
