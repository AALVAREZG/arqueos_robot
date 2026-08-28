"""
Centralized, phase-oriented logging for the Arqueos Robot.

One readable stream, from the producer's (sical-robot) point of view: every
line of an operation is correlated to its task id and tagged with the
lifecycle PHASE, so you can follow exactly where a task is and, on failure,
which phase broke and why.

Phases (arqueo lifecycle):

    RECEIVED   task message arrived from the producer
    PARSED     operation details extracted (op#, importe, fecha, ...)
    DUP-CHECK  duplicate pre-check (skipped / clear / DUPLICATE)
    SICAL-OPEN SICAL window opened
    FILL       main panel + N aplicaciones written
    VALIDATE   operation validated -> num_operacion
    CONTABLE   contable PDF captured (new flow) or printed (legacy)
    RESULT     result (+ contable_document) returned to the producer
    DONE       outcome OK (with duration)
    FAILED     outcome KO -- the message names the phase + cause

Usage:

    from logging_setup import get_logger, phase, ok, warn, fail, detail, bind_task

    log = get_logger(__name__)
    bind_task(task_id)                       # once, when the task arrives
    phase(log, "DUP-CHECK", "no similar records - proceeding")
    fail(log, "CONTABLE", "sical_capture: 'Guardar como' not found")

Console level is INFO by default (the clean phase stream). Set
ARQUEOS_LOG_LEVEL=DEBUG for the verbose internals (keystrokes, payloads).
"""

import contextvars
import logging
import gui_log_filter
import os
import sys

# --- task correlation -------------------------------------------------------

_current_task = contextvars.ContextVar('arqueos_task', default='-')


def bind_task(task_id):
    """Bind the current task id so every phase line is correlated to it.
    Call once when a task is received; pass falsy / call unbind_task() when
    the task ends."""
    _current_task.set(_short(task_id) if task_id else '-')


def unbind_task():
    _current_task.set('-')


def _short(task_id, width=20):
    s = str(task_id)
    return s if len(s) <= width else (s[:width - 2] + '..')


# --- formatters -------------------------------------------------------------

def _task_of(record):
    return getattr(record, 'task', None) or _current_task.get()


def _phase_of(record):
    return getattr(record, 'phase', '') or ''


class _ConsoleFormatter(logging.Formatter):
    """`HH:MM:SS LEVEL  task=<id>  <PHASE>       message` (ASCII-safe)."""

    def format(self, record):
        ts = self.formatTime(record, '%H:%M:%S')
        line = (f"{ts} {record.levelname:<5} "
                f"task={_task_of(record):<20} "
                f"{_phase_of(record):<10} "
                f"{record.getMessage()}")
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _GuiFormatter(logging.Formatter):
    """Compact form for the GUI Activity Log. status_manager.add_log already
    prefixes `[HH:MM:SS] [LEVEL]`, so timestamp/level are omitted here."""

    def format(self, record):
        ph = _phase_of(record)
        head = f"{_task_of(record)} {ph}".strip()
        return f"{head} | {record.getMessage()}" if head else record.getMessage()


# Third-party libraries that flood the stream; pinned to WARNING.
_NOISY = ('pika', 'comtypes', 'urllib3', 'PIL', 'robocorp', 'RPA',
          'asyncio', 'charset_normalizer')

_configured = False


def configure_logging(gui_handler=None):
    """Install the single console handler (and optionally a GUI handler).
    Idempotent: safe to call from whichever entrypoint starts first
    (main.py headless, or the GUI)."""
    global _configured
    level_name = os.getenv('ARQUEOS_LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # handlers do the gating

    if not _configured:
        # Drop any pre-existing handlers (e.g. a stray basicConfig) so we
        # don't double-print.
        for h in list(root.handlers):
            root.removeHandler(h)

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(_ConsoleFormatter())
        console.set_name('arqueos_console')
        root.addHandler(console)

        for noisy in _NOISY:
            logging.getLogger(noisy).setLevel(logging.WARNING)

        _configured = True

    if gui_handler is not None and not any(
            getattr(h, 'name', '') == 'arqueos_gui' for h in root.handlers):
        # La ventana recibe solo el flujo limpio de fases (INFO+) y solo de
        # codigo nuestro. `_NOISY` baja a WARNING a los sospechosos habituales,
        # pero es una lista negra: no cubre a `fontTools` -una veintena de
        # loggers el solo-, `RobotFramework`, `WDM`... ni a un WARNING de
        # robocorp. El filtro de lista blanca cierra eso (ver gui_log_filter).
        gui_handler.setFormatter(_GuiFormatter())
        gui_handler.set_name('arqueos_gui')
        gui_log_filter.install(gui_handler, level=logging.INFO)
        root.addHandler(gui_handler)

    return root


def get_logger(name):
    return logging.getLogger(name)


# --- phase API --------------------------------------------------------------

def _emit(logger, level, phase_name, msg, exc=False):
    logger.log(level, msg,
               extra={'task': _current_task.get(), 'phase': phase_name},
               exc_info=exc)


def phase(logger, phase_name, msg):
    """A normal lifecycle milestone (INFO)."""
    _emit(logger, logging.INFO, phase_name, msg)


def ok(logger, phase_name, msg):
    """A phase completed successfully (INFO)."""
    _emit(logger, logging.INFO, phase_name, msg)


def warn(logger, phase_name, msg):
    """A non-fatal anomaly within a phase (WARNING)."""
    _emit(logger, logging.WARNING, phase_name, msg)


def fail(logger, phase_name, msg, exc=False):
    """Terminal failure: names the phase and the cause (ERROR)."""
    _emit(logger, logging.ERROR, phase_name,
          f"FAILED at {phase_name} -- {msg}", exc=exc)


def detail(logger, phase_name, msg):
    """Verbose internal (DEBUG): keystrokes, payloads, element paths.
    Hidden unless ARQUEOS_LOG_LEVEL=DEBUG."""
    _emit(logger, logging.DEBUG, phase_name, msg)
