# SICAL Arqueos Robot - GUI Status Monitor

## Overview

The GUI Status Monitor provides a real-time graphical interface for monitoring the Arqueos Robot service. It displays task statistics, current execution status, and activity logs in an easy-to-use Windows application.

## Features

### 📊 Real-Time Monitoring
- **Service Status**: Shows whether the service is running or stopped
- **RabbitMQ Connection**: Displays connection status to the message queue
- **Uptime Tracking**: Shows how long the service has been running

### 📈 Task Statistics
- **Pending**: Number of tasks waiting to be processed
- **Processing**: Currently executing tasks
- **Completed**: Successfully processed tasks
- **Failed**: Tasks that encountered errors
- **Success Rate**: Percentage of successful operations

### 🔄 Current Task Display
- **Task ID**: Identifier of the current task
- **Operation Number**: SICAL operation number being processed
- **Duration**: How long the current task has been running
- **Amount**: Transaction amount (€)
- **Current Step**: Detailed progress information (e.g., "Opening SICAL window", "Processing line items")

### 📝 Activity Log
- Real-time log display with color-coded messages
- INFO (black), WARNING (orange), ERROR (red), DEBUG (gray)
- Auto-scrolling to show latest messages
- Maintains last 200 log entries

### 🎛️ Controls
- **Start Service**: Launch the RabbitMQ consumer and start processing tasks
- **Stop Service**: Gracefully stop the consumer
- **Clear Stats**: Reset statistics counters

## How to Run

### Option 1: Direct Python Execution
```bash
python arqueos_gui.py
```

### Option 2: Using the Launcher Script
```bash
python run_gui.py
```

### Option 3: On Windows (after packaging)
```bash
arqueos_gui.exe
```

## Architecture

The GUI is implemented as a **wrapper** around the existing consumer code with minimal modifications:

```
┌─────────────────────────────────────┐
│   arqueos_gui.py (GUI Layer)        │
│   - tkinter interface                │
│   - Display updates every 500ms      │
│   - Controls (Start/Stop)            │
└─────────────┬───────────────────────┘
              │
              ├─ reads from
              │
┌─────────────▼───────────────────────┐
│   status_manager.py                  │
│   - Thread-safe status storage       │
│   - Statistics tracking              │
│   - Log message buffer               │
└─────────────▲───────────────────────┘
              │
              ├─ writes to (via callbacks)
              │
┌─────────────┴───────────────────────┐
│   arqueo_task_consumer.py            │
│   + STATUS_CALLBACK hooks (minimal)  │
│   - task_received, task_started      │
│   - task_completed, task_failed      │
│   - connected, disconnected          │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│   arqueo_tasks.py                    │
│   + TASK_CALLBACK hooks (minimal)    │
│   - Progress step updates            │
│   - "Preparing data", "Opening       │
│     SICAL", "Processing", etc.       │
└─────────────────────────────────────┘
```

## Code Changes Summary

### New Files Created
1. **`status_manager.py`** - Thread-safe state management
2. **`arqueos_gui.py`** - Main GUI application
3. **`run_gui.py`** - Launcher script

### Minimal Hooks Added to Existing Code

#### `arqueo_task_consumer.py` (9 lines added)
- Added `STATUS_CALLBACK` global variable
- Added `set_status_callback()` function
- Added 7 callback invocations at key points:
  - `connecting`, `connected`, `disconnected`
  - `task_received`, `task_started`
  - `task_completed`, `task_failed`

#### `arqueo_tasks.py` (13 lines added)
- Added `TASK_CALLBACK` global variable
- Added `set_task_callback()` function
- Added 5 progress callbacks:
  - "Preparing operation data"
  - "Opening SICAL window"
  - "Processing arqueo operation"
  - "Validating operation"
  - "Finalizing operation"

### Backward Compatibility
- All hooks are **optional** - the code works exactly as before if GUI is not used
- No changes to existing function signatures
- No changes to business logic
- The consumer can still run standalone: `python arqueo_task_consumer.py`

## Packaging for Distribution

To create a standalone Windows executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --onefile --windowed --name "ArqueosRobot" arqueos_gui.py

# The .exe will be in the dist/ folder
```

### PyInstaller Options Explained:
- `--onefile`: Creates a single executable file
- `--windowed`: No console window (GUI-only)
- `--name "ArqueosRobot"`: Name of the executable

## Development vs. Production

### Development Mode
- Run from Python: `python arqueos_gui.py`
- Logs are visible in console
- Easy to debug and modify

### Production Mode (Packaged .exe)
- Double-click to run
- Professional Windows application
- No console window
- Suitable for end-users

## Requirements

### Python Dependencies
- `tkinter` (built into Python)
- `pika` (for RabbitMQ)
- `robocorp` (for RPA automation)
- `robocorp-windows` (for SICAL window automation)

All existing dependencies remain unchanged.

## Troubleshooting

### GUI doesn't start
- Check that tkinter is installed: `python -m tkinter`
- Verify Python version: Python 3.10+ required

### Service won't connect
- Verify RabbitMQ credentials in `.env` file
- Check that RabbitMQ server is running and accessible

### No tasks appearing
- Confirm messages are being sent to `sical_queue.arqueo` queue
- Check RabbitMQ management interface for queue status

### GUI freezes
- This shouldn't happen as the consumer runs in a separate thread
- If it does, restart the application

## Future Enhancements

Possible improvements (not yet implemented):
- Export statistics to CSV
- Task history viewer with filtering
- Configuration panel for RabbitMQ settings
- Charts and graphs for performance metrics
- System tray icon for background operation
- Email/SMS notifications on errors

## License

Same as the main Arqueos Robot project.
