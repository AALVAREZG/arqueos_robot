"""
Thread-safe status manager for monitoring the Arqueos Robot service.

This module provides a singleton StatusManager that maintains the current state
of the service, including task statistics, current execution status, and connection state.
"""

import threading
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class TaskInfo:
    """Information about a currently executing task."""
    task_id: str
    operation_number: Optional[str] = None
    amount: Optional[float] = None
    start_time: datetime = field(default_factory=datetime.now)
    status: str = "processing"
    current_step: str = ""

    # Additional detailed information
    date: Optional[str] = None  # fecha
    cash_register: Optional[str] = None  # caja
    file_reference: Optional[str] = None  # expediente
    third_party: Optional[str] = None  # tercero
    nature: Optional[str] = None  # naturaleza (4=expenses, 5=income)
    description: Optional[str] = None  # resumen
    total_line_items: int = 0  # Total number of aplicaciones
    current_line_item: int = 0  # Current line item being processed
    line_item_details: Optional[str] = None  # Current line item description

    def duration(self) -> float:
        """Returns the duration in seconds since task started."""
        return (datetime.now() - self.start_time).total_seconds()

    def nature_display(self) -> str:
        """Returns a human-readable nature label."""
        if self.nature == '4':
            return "💸 Expenses (Gastos)"
        elif self.nature == '5':
            return "💰 Income (Ingresos)"
        return "Unknown"


class StatusManager:
    """
    Thread-safe singleton for managing service status across threads.

    This manager is updated by the worker thread (consumer) via callbacks
    and read by the GUI thread for display updates.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the status manager (only once)."""
        if self._initialized:
            return

        self._initialized = True
        self._data_lock = threading.Lock()

        # Service state
        self.service_running = False
        self.rabbitmq_connected = False

        # Task statistics
        self.stats = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'total_processed': 0
        }

        # Current task
        self.current_task: Optional[TaskInfo] = None

        # Log messages (circular buffer)
        self.log_messages = []
        self.max_log_messages = 200

        # Session stats (reset on service start)
        self.session_start_time: Optional[datetime] = None

    def update_service_status(self, running: bool):
        """Update the service running status."""
        with self._data_lock:
            self.service_running = running
            if running and self.session_start_time is None:
                self.session_start_time = datetime.now()

    def update_rabbitmq_status(self, connected: bool):
        """Update RabbitMQ connection status."""
        with self._data_lock:
            self.rabbitmq_connected = connected

    def task_received(self, task_id: str):
        """Called when a new task is received from the queue."""
        with self._data_lock:
            self.stats['pending'] += 1

    def task_started(self, task_id: str, operation_number: Optional[str] = None,
                     amount: Optional[float] = None, **kwargs):
        """Called when a task starts processing."""
        with self._data_lock:
            if self.stats['pending'] > 0:
                self.stats['pending'] -= 1
            self.stats['processing'] += 1

            self.current_task = TaskInfo(
                task_id=task_id,
                operation_number=operation_number,
                amount=amount,
                start_time=datetime.now(),
                date=kwargs.get('date'),
                cash_register=kwargs.get('cash_register'),
                file_reference=kwargs.get('file_reference'),
                third_party=kwargs.get('third_party'),
                nature=kwargs.get('nature'),
                description=kwargs.get('description'),
                total_line_items=kwargs.get('total_line_items', 0)
            )

    def task_progress(self, step: str, **kwargs):
        """Update the current step of the task being processed."""
        with self._data_lock:
            if self.current_task:
                self.current_task.current_step = step

                # Update line item progress if provided
                if 'current_line_item' in kwargs:
                    self.current_task.current_line_item = kwargs['current_line_item']
                if 'line_item_details' in kwargs:
                    self.current_task.line_item_details = kwargs['line_item_details']

    def task_completed(self, task_id: str, success: bool = True):
        """Called when a task completes (success or failure)."""
        with self._data_lock:
            if self.stats['processing'] > 0:
                self.stats['processing'] -= 1

            if success:
                self.stats['completed'] += 1
            else:
                self.stats['failed'] += 1

            self.stats['total_processed'] += 1

            # Clear current task if it matches
            if self.current_task and self.current_task.task_id == task_id:
                self.current_task = None

    def add_log(self, message: str, level: str = "INFO"):
        """Add a log message to the circular buffer."""
        with self._data_lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}"

            self.log_messages.append(log_entry)

            # Keep only the last N messages
            if len(self.log_messages) > self.max_log_messages:
                self.log_messages.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """
        Get a snapshot of the current status (thread-safe).

        Returns a dictionary with all current status information.
        """
        with self._data_lock:
            # Calculate success rate
            total = self.stats['completed'] + self.stats['failed']
            success_rate = (self.stats['completed'] / total * 100) if total > 0 else 0.0

            # Get current task info
            current_task_info = None
            if self.current_task:
                current_task_info = {
                    'task_id': self.current_task.task_id,
                    'operation_number': self.current_task.operation_number,
                    'amount': self.current_task.amount,
                    'duration': self.current_task.duration(),
                    'current_step': self.current_task.current_step,
                    'date': self.current_task.date,
                    'cash_register': self.current_task.cash_register,
                    'file_reference': self.current_task.file_reference,
                    'third_party': self.current_task.third_party,
                    'nature': self.current_task.nature,
                    'nature_display': self.current_task.nature_display(),
                    'description': self.current_task.description,
                    'total_line_items': self.current_task.total_line_items,
                    'current_line_item': self.current_task.current_line_item,
                    'line_item_details': self.current_task.line_item_details
                }

            # Calculate session uptime
            uptime = None
            if self.session_start_time:
                uptime = (datetime.now() - self.session_start_time).total_seconds()

            return {
                'service_running': self.service_running,
                'rabbitmq_connected': self.rabbitmq_connected,
                'stats': self.stats.copy(),
                'success_rate': success_rate,
                'current_task': current_task_info,
                'recent_logs': self.log_messages[-50:].copy(),  # Last 50 logs
                'uptime': uptime
            }

    def reset_stats(self):
        """Reset statistics (useful when restarting the service)."""
        with self._data_lock:
            self.stats = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0,
                'total_processed': 0
            }
            self.current_task = None
            self.session_start_time = None

    def get_logs(self, count: int = 50) -> list:
        """Get the most recent log messages."""
        with self._data_lock:
            return self.log_messages[-count:].copy()


# Global singleton instance
status_manager = StatusManager()
