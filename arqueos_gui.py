"""
SICAL Arqueos Robot - GUI Status Monitor

A tkinter-based GUI for monitoring the Arqueos Robot service.
Provides real-time status updates, task monitoring, and service control.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import logging
from datetime import datetime
from typing import Optional

from status_manager import status_manager


class LogHandler(logging.Handler):
    """Custom logging handler that sends logs to the status manager."""

    def emit(self, record):
        """Emit a log record to the status manager."""
        try:
            msg = self.format(record)
            status_manager.add_log(msg, record.levelname)
        except Exception:
            self.handleError(record)


class ArqueosGUI:
    """Main GUI application for the Arqueos Robot service."""

    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("SICAL Arqueos Robot - Status Monitor")
        self.root.geometry("900x850")
        self.root.resizable(True, True)

        # Consumer thread reference
        self.consumer_thread: Optional[threading.Thread] = None
        self.consumer = None

        # Setup logging to capture logs
        self.setup_logging()

        # Create UI
        self.create_widgets()

        # Start update loop
        self.update_display()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_logging(self):
        """Setup logging to capture all logs for display."""
        # Get root logger
        root_logger = logging.getLogger()

        # Add our custom handler
        gui_handler = LogHandler()
        gui_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s - %(message)s')
        gui_handler.setFormatter(formatter)
        root_logger.addHandler(gui_handler)

    def create_widgets(self):
        """Create all GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)  # Log panel expands

        # Title
        title_label = ttk.Label(
            main_frame,
            text="SICAL Arqueos Robot - Status Monitor",
            font=("Segoe UI", 14, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Status Panel
        self.create_status_panel(main_frame)

        # Statistics Panel
        self.create_statistics_panel(main_frame)

        # Current Task Panel
        self.create_current_task_panel(main_frame)

        # Control Buttons
        self.create_control_panel(main_frame)

        # Log Panel
        self.create_log_panel(main_frame)

    def create_status_panel(self, parent):
        """Create the service status panel."""
        status_frame = ttk.LabelFrame(parent, text="Service Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Service status
        ttk.Label(status_frame, text="Service:").grid(row=0, column=0, sticky=tk.W)
        self.service_status_label = ttk.Label(
            status_frame,
            text="● STOPPED",
            foreground="red",
            font=("Segoe UI", 10, "bold")
        )
        self.service_status_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))

        # RabbitMQ status
        ttk.Label(status_frame, text="RabbitMQ:").grid(row=0, column=2, sticky=tk.W)
        self.rabbitmq_status_label = ttk.Label(
            status_frame,
            text="● DISCONNECTED",
            foreground="red",
            font=("Segoe UI", 10, "bold")
        )
        self.rabbitmq_status_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        # Uptime
        ttk.Label(status_frame, text="Uptime:").grid(row=0, column=4, sticky=tk.W, padx=(20, 0))
        self.uptime_label = ttk.Label(status_frame, text="--:--:--")
        self.uptime_label.grid(row=0, column=5, sticky=tk.W, padx=5)

    def create_statistics_panel(self, parent):
        """Create the statistics panel."""
        stats_frame = ttk.LabelFrame(parent, text="📊 Statistics", padding="10")
        stats_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Configure columns
        for i in range(5):
            stats_frame.columnconfigure(i, weight=1)

        # Pending
        ttk.Label(stats_frame, text="Pending:", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky=tk.W
        )
        self.pending_label = ttk.Label(
            stats_frame,
            text="0",
            font=("Segoe UI", 11, "bold"),
            foreground="orange"
        )
        self.pending_label.grid(row=1, column=0, sticky=tk.W)

        # Processing
        ttk.Label(stats_frame, text="Processing:", font=("Segoe UI", 9)).grid(
            row=0, column=1, sticky=tk.W
        )
        self.processing_label = ttk.Label(
            stats_frame,
            text="0",
            font=("Segoe UI", 11, "bold"),
            foreground="blue"
        )
        self.processing_label.grid(row=1, column=1, sticky=tk.W)

        # Completed
        ttk.Label(stats_frame, text="Completed:", font=("Segoe UI", 9)).grid(
            row=0, column=2, sticky=tk.W
        )
        self.completed_label = ttk.Label(
            stats_frame,
            text="0",
            font=("Segoe UI", 11, "bold"),
            foreground="green"
        )
        self.completed_label.grid(row=1, column=2, sticky=tk.W)

        # Failed
        ttk.Label(stats_frame, text="Failed:", font=("Segoe UI", 9)).grid(
            row=0, column=3, sticky=tk.W
        )
        self.failed_label = ttk.Label(
            stats_frame,
            text="0",
            font=("Segoe UI", 11, "bold"),
            foreground="red"
        )
        self.failed_label.grid(row=1, column=3, sticky=tk.W)

        # Success Rate
        ttk.Label(stats_frame, text="Success Rate:", font=("Segoe UI", 9)).grid(
            row=0, column=4, sticky=tk.W
        )
        self.success_rate_label = ttk.Label(
            stats_frame,
            text="0.0%",
            font=("Segoe UI", 11, "bold")
        )
        self.success_rate_label.grid(row=1, column=4, sticky=tk.W)

    def create_current_task_panel(self, parent):
        """Create the current task panel."""
        task_frame = ttk.LabelFrame(parent, text="🔄 Current Task", padding="10")
        task_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Configure grid columns for better layout
        task_frame.columnconfigure(1, weight=1)
        task_frame.columnconfigure(3, weight=1)

        # Task info labels
        self.current_task_label = ttk.Label(
            task_frame,
            text="No task currently processing",
            font=("Segoe UI", 9, "bold"),
            foreground="gray"
        )
        self.current_task_label.grid(row=0, column=0, sticky=tk.W, columnspan=4, pady=(0, 5))

        # Row 1: Operation number and Date
        ttk.Label(task_frame, text="Operation:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky=tk.W
        )
        self.operation_label = ttk.Label(task_frame, text="--")
        self.operation_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 15))

        ttk.Label(task_frame, text="Date:", font=("Segoe UI", 9)).grid(
            row=1, column=2, sticky=tk.W
        )
        self.date_label = ttk.Label(task_frame, text="--")
        self.date_label.grid(row=1, column=3, sticky=tk.W, padx=5)

        # Row 2: Duration and Cash Register
        ttk.Label(task_frame, text="Duration:", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky=tk.W
        )
        self.duration_label = ttk.Label(task_frame, text="--")
        self.duration_label.grid(row=2, column=1, sticky=tk.W, padx=(5, 15))

        ttk.Label(task_frame, text="Cash Register:", font=("Segoe UI", 9)).grid(
            row=2, column=2, sticky=tk.W
        )
        self.cash_register_label = ttk.Label(task_frame, text="--")
        self.cash_register_label.grid(row=2, column=3, sticky=tk.W, padx=5)

        # Row 3: Amount and Nature
        ttk.Label(task_frame, text="Amount:", font=("Segoe UI", 9)).grid(
            row=3, column=0, sticky=tk.W
        )
        self.amount_label = ttk.Label(task_frame, text="--")
        self.amount_label.grid(row=3, column=1, sticky=tk.W, padx=(5, 15))

        ttk.Label(task_frame, text="Type:", font=("Segoe UI", 9)).grid(
            row=3, column=2, sticky=tk.W
        )
        self.nature_label = ttk.Label(task_frame, text="--")
        self.nature_label.grid(row=3, column=3, sticky=tk.W, padx=5)

        # Row 4: Third Party (full width)
        ttk.Label(task_frame, text="Third Party:", font=("Segoe UI", 9)).grid(
            row=4, column=0, sticky=tk.W
        )
        self.third_party_label = ttk.Label(task_frame, text="--", wraplength=600)
        self.third_party_label.grid(row=4, column=1, sticky=tk.W, columnspan=3, padx=5)

        # Row 5: Description (full width)
        ttk.Label(task_frame, text="Description:", font=("Segoe UI", 9)).grid(
            row=5, column=0, sticky=tk.W
        )
        self.description_label = ttk.Label(task_frame, text="--", wraplength=600)
        self.description_label.grid(row=5, column=1, sticky=tk.W, columnspan=3, padx=5)

        # Separator
        ttk.Separator(task_frame, orient='horizontal').grid(
            row=6, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=8
        )

        # Row 7: Line items progress
        ttk.Label(task_frame, text="Line Items:", font=("Segoe UI", 9, "bold")).grid(
            row=7, column=0, sticky=tk.W
        )
        self.line_items_label = ttk.Label(task_frame, text="--", font=("Segoe UI", 9))
        self.line_items_label.grid(row=7, column=1, sticky=tk.W, columnspan=3, padx=5)

        # Row 8: Current line item details
        ttk.Label(task_frame, text="Current Item:", font=("Segoe UI", 9)).grid(
            row=8, column=0, sticky=tk.W
        )
        self.line_item_details_label = ttk.Label(task_frame, text="--", wraplength=600)
        self.line_item_details_label.grid(row=8, column=1, sticky=tk.W, columnspan=3, padx=5)

        # Row 9: Current step
        ttk.Label(task_frame, text="Status:", font=("Segoe UI", 9)).grid(
            row=9, column=0, sticky=tk.W
        )
        self.step_label = ttk.Label(task_frame, text="--", wraplength=600, foreground="blue")
        self.step_label.grid(row=9, column=1, sticky=tk.W, columnspan=3, padx=5)

    def create_control_panel(self, parent):
        """Create the control buttons panel."""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=5, column=0, columnspan=2, pady=10)

        # Start button
        self.start_button = ttk.Button(
            control_frame,
            text="▶ Start Service",
            command=self.start_service,
            width=20
        )
        self.start_button.grid(row=0, column=0, padx=5)

        # Stop button
        self.stop_button = ttk.Button(
            control_frame,
            text="⏹ Stop Service",
            command=self.stop_service,
            state=tk.DISABLED,
            width=20
        )
        self.stop_button.grid(row=0, column=1, padx=5)

        # Clear stats button
        self.clear_button = ttk.Button(
            control_frame,
            text="🗑 Clear Stats",
            command=self.clear_stats,
            width=20
        )
        self.clear_button.grid(row=0, column=2, padx=5)

    def create_log_panel(self, parent):
        """Create the log display panel."""
        log_frame = ttk.LabelFrame(parent, text="📝 Activity Log", padding="5")
        log_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Log text widget with scrollbar
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            width=80,
            height=15,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure log text tags for colors
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("DEBUG", foreground="gray")

    def start_service(self):
        """Start the consumer service in a background thread."""
        if self.consumer_thread and self.consumer_thread.is_alive():
            status_manager.add_log("Service is already running", "WARNING")
            return

        status_manager.add_log("Starting Arqueos Robot service...", "INFO")
        status_manager.update_service_status(True)
        status_manager.reset_stats()

        # Import consumer here to set up callbacks first
        from arqueo_task_consumer import ArqueoConsumer, set_status_callback
        from arqueo_tasks import set_task_callback

        # Set up callbacks
        set_status_callback(self.status_callback)
        set_task_callback(self.task_callback)

        # Create consumer instance
        self.consumer = ArqueoConsumer()

        # Start consumer in background thread
        self.consumer_thread = threading.Thread(
            target=self.run_consumer,
            daemon=True,
            name="ConsumerThread"
        )
        self.consumer_thread.start()

        # Update button states
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def run_consumer(self):
        """Run the consumer (blocking call in background thread)."""
        try:
            self.consumer.start()
        except Exception as e:
            status_manager.add_log(f"Consumer error: {e}", "ERROR")
            status_manager.update_service_status(False)

    def stop_service(self):
        """Stop the consumer service."""
        if not self.consumer or not self.consumer_thread or not self.consumer_thread.is_alive():
            status_manager.add_log("Service is not running", "WARNING")
            return

        status_manager.add_log("Stopping Arqueos Robot service...", "INFO")

        # Stop consumer gracefully
        if self.consumer:
            self.consumer.stop()

        status_manager.update_service_status(False)
        status_manager.update_rabbitmq_status(False)

        # Update button states
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def clear_stats(self):
        """Clear statistics."""
        status_manager.reset_stats()
        status_manager.add_log("Statistics cleared", "INFO")

    def status_callback(self, event: str, **kwargs):
        """
        Callback from consumer for status updates.

        Events:
        - 'connecting': Attempting to connect to RabbitMQ
        - 'connected': Successfully connected to RabbitMQ
        - 'disconnected': Disconnected from RabbitMQ
        - 'task_received': New task received from queue
        - 'task_started': Task processing started
        - 'task_completed': Task completed successfully
        - 'task_failed': Task failed
        """
        if event == 'connected':
            status_manager.update_rabbitmq_status(True)
        elif event == 'disconnected':
            status_manager.update_rabbitmq_status(False)
        elif event == 'task_received':
            task_id = kwargs.get('task_id', 'unknown')
            status_manager.task_received(task_id)
        elif event == 'task_started':
            task_id = kwargs.get('task_id', 'unknown')
            operation_number = kwargs.get('operation_number')
            amount = kwargs.get('amount')

            # DEBUG: Log what we received
            status_manager.add_log(f"GUI received task_started with keys: {list(kwargs.keys())}", "DEBUG")
            status_manager.add_log(f"Date: {kwargs.get('date')}, Cash: {kwargs.get('cash_register')}, "
                                  f"Third Party: {kwargs.get('third_party')}, Nature: {kwargs.get('nature')}", "DEBUG")

            # Pass all additional kwargs (date, cash_register, third_party, nature, etc.)
            # Remove the keys we've already extracted to avoid duplicate arguments
            additional_kwargs = {k: v for k, v in kwargs.items()
                               if k not in ('task_id', 'operation_number', 'amount')}

            status_manager.add_log(f"Passing additional_kwargs keys: {list(additional_kwargs.keys())}", "DEBUG")
            status_manager.task_started(task_id, operation_number, amount, **additional_kwargs)
        elif event == 'task_completed':
            task_id = kwargs.get('task_id', 'unknown')
            status_manager.task_completed(task_id, success=True)
        elif event == 'task_failed':
            task_id = kwargs.get('task_id', 'unknown')
            status_manager.task_completed(task_id, success=False)

    def task_callback(self, event: str, **kwargs):
        """
        Callback from task processor for detailed progress updates.

        Events:
        - 'step': Current processing step
        """
        if event == 'step':
            step = kwargs.get('step', '')
            # Pass all kwargs except 'step' itself (current_line_item, line_item_details, etc.)
            additional_kwargs = {k: v for k, v in kwargs.items() if k != 'step'}
            status_manager.task_progress(step, **additional_kwargs)

    def update_display(self):
        """Update the display with current status (called periodically)."""
        # Get current status
        status = status_manager.get_status()

        # Update service status
        if status['service_running']:
            self.service_status_label.config(text="● RUNNING", foreground="green")
        else:
            self.service_status_label.config(text="● STOPPED", foreground="red")

        # Update RabbitMQ status
        if status['rabbitmq_connected']:
            self.rabbitmq_status_label.config(text="● CONNECTED", foreground="green")
        else:
            self.rabbitmq_status_label.config(text="● DISCONNECTED", foreground="red")

        # Update uptime
        if status['uptime']:
            hours = int(status['uptime'] // 3600)
            minutes = int((status['uptime'] % 3600) // 60)
            seconds = int(status['uptime'] % 60)
            self.uptime_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self.uptime_label.config(text="--:--:--")

        # Update statistics
        stats = status['stats']
        self.pending_label.config(text=str(stats['pending']))
        self.processing_label.config(text=str(stats['processing']))
        self.completed_label.config(text=str(stats['completed']))
        self.failed_label.config(text=str(stats['failed']))
        self.success_rate_label.config(text=f"{status['success_rate']:.1f}%")

        # Update current task
        current_task = status['current_task']
        if current_task:
            task_id = current_task['task_id'][:16] + "..." if len(current_task['task_id']) > 16 else current_task['task_id']
            self.current_task_label.config(
                text=f"Processing: {task_id}",
                foreground="blue"
            )

            # Basic info
            operation = current_task['operation_number'] or "--"
            self.operation_label.config(text=operation)

            date = current_task.get('date') or "--"
            self.date_label.config(text=date)

            duration = current_task['duration']
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            self.duration_label.config(text=f"{minutes:02d}:{seconds:02d}")

            cash_register = current_task.get('cash_register') or "--"
            self.cash_register_label.config(text=cash_register)

            amount = current_task['amount']
            if amount is not None:
                self.amount_label.config(text=f"€{amount:.2f}")
            else:
                self.amount_label.config(text="--")

            nature_display = current_task.get('nature_display') or "--"
            self.nature_label.config(text=nature_display)

            # Detailed info
            third_party = current_task.get('third_party') or "--"
            self.third_party_label.config(text=third_party)

            description = current_task.get('description') or "--"
            self.description_label.config(text=description)

            # Line items progress
            total_items = current_task.get('total_line_items', 0)
            current_item = current_task.get('current_line_item', 0)
            if total_items > 0:
                progress_text = f"{current_item} of {total_items}"
                if current_item > 0:
                    percentage = (current_item / total_items) * 100
                    progress_text += f" ({percentage:.0f}%)"
                self.line_items_label.config(text=progress_text)
            else:
                self.line_items_label.config(text="--")

            line_details = current_task.get('line_item_details') or "--"
            self.line_item_details_label.config(text=line_details)

            step = current_task['current_step'] or "Processing..."
            self.step_label.config(text=step)
        else:
            self.current_task_label.config(
                text="No task currently processing",
                foreground="gray"
            )
            self.operation_label.config(text="--")
            self.date_label.config(text="--")
            self.duration_label.config(text="--")
            self.cash_register_label.config(text="--")
            self.amount_label.config(text="--")
            self.nature_label.config(text="--")
            self.third_party_label.config(text="--")
            self.description_label.config(text="--")
            self.line_items_label.config(text="--")
            self.line_item_details_label.config(text="--")
            self.step_label.config(text="--")

        # Update logs
        recent_logs = status['recent_logs']
        if recent_logs:
            # Get current text
            current_logs = self.log_text.get("1.0", tk.END).strip()
            new_logs = "\n".join(recent_logs)

            # Only update if changed
            if current_logs != new_logs:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.delete("1.0", tk.END)

                for log in recent_logs:
                    # Determine tag based on log level
                    tag = "INFO"
                    if "[ERROR]" in log:
                        tag = "ERROR"
                    elif "[WARNING]" in log:
                        tag = "WARNING"
                    elif "[DEBUG]" in log:
                        tag = "DEBUG"

                    self.log_text.insert(tk.END, log + "\n", tag)

                # Auto-scroll to bottom
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)

        # Schedule next update (500ms)
        self.root.after(500, self.update_display)

    def on_closing(self):
        """Handle window closing event."""
        if self.consumer and self.consumer_thread and self.consumer_thread.is_alive():
            status_manager.add_log("Stopping service before exit...", "INFO")
            self.stop_service()
            # Give it a moment to cleanup
            self.root.after(1000, self.root.destroy)
        else:
            self.root.destroy()


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = ArqueosGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
