# Arqueos Robot - SICAL II Automation

![Tests](https://github.com/AALVAREZG/arqueos_robot/workflows/Tests/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Robotic Process Automation (RPA) application for automating "arqueos" (accounting reconciliations) operations in the SICAL II financial management system used by Spanish municipal administrations.

## Overview

This robot automates complex financial workflows by:
- Receiving operation requests via RabbitMQ message queue
- Automating SICAL II desktop application interactions
- Processing accounting line items (aplicaciones contables)
- Validating and reconciling financial transactions
- Returning operation results asynchronously

**Target System**: SICAL II 4.2 (Sistema de Información Centralizado de la Administración Local)
**Architecture**: Message-driven RPA with queue-based task processing

## Features

- 🔄 **Asynchronous Processing** - RabbitMQ-based message queue
- 🖥️ **Windows UI Automation** - Robocorp framework for SICAL interaction
- 🏦 **Municipal Finance** - Supports Spanish local government accounting codes
- 📊 **Multiple Operation Types** - Handles naturaleza 4 and 5 operations
- ✅ **Validation & Reconciliation** - Automatic amount verification
- 📝 **Comprehensive Logging** - Detailed operation tracking
- 🧪 **Tested** - Comprehensive test suite with >80% coverage
- 🎨 **GUI Status Monitor** - Real-time monitoring with tabbed interface
- 📜 **Task History** - SQLite database with complete audit trail
- 📤 **Export Capabilities** - Export to Excel, JSON, and CSV

## Prerequisites

### System Requirements
- **Operating System**: Windows (SICAL II is Windows-only)
- **Python**: 3.10.12 or higher
- **SICAL II**: Version 4.2 mtec40
- **RabbitMQ**: Message broker server

### Software Dependencies
- Robocorp RPA Framework
- Python 3.10+
- RabbitMQ Server

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AALVAREZG/arqueos_robot.git
cd arqueos_robot
```

### 2. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n arqueos python=3.10.12
conda activate arqueos
```

### 3. Install Dependencies

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or using conda environment
conda env create -f conda.yaml
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# .env
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=your_username
RABBITMQ_PASS=your_password
```

**Security Note**: Never commit `.env` file to version control.

## Usage

### Starting the Robot

The robot can run in two modes:

#### GUI Mode (Recommended)

Run with graphical interface for monitoring and control:

```bash
python arqueos_gui.py
# or
python run_gui.py
```

Features:
- Real-time monitoring dashboard
- Service control (start/stop)
- Complete task history with search
- Export capabilities (Excel, JSON, CSV)
- Visual task progress tracking

See [GUI Status Monitor](#gui-status-monitor) section for detailed documentation.

#### CLI Mode (Headless)

Run without GUI for server deployments:

```bash
python main.py
```

The robot will:
1. Connect to RabbitMQ
2. Listen on the `sical_queue.arqueo` queue
3. Process incoming arqueo operations
4. Send results back to the reply queue
5. Log to console/file

### Message Format

Send messages to the `sical_queue.arqueo` queue with the following structure:

```json
{
  "task_id": "204_08112024_5000_MPTOST",
  "operation_data": {
    "operation": {
      "tipo": "arqueo",
      "detalle": {
        "fecha": "08112024",
        "caja": "204",
        "expediente": "",
        "tercero": "43000000M",
        "naturaleza": "5",
        "texto_sical": [
          {
            "tcargo": "RECAUDADO TRIBUTOS VARIOS C60"
          }
        ],
        "aplicaciones": [
          {
            "year": "2024",
            "economica": "30012",
            "proyecto": "",
            "contraido": true,
            "base_imponible": 0.0,
            "tipo": 0.0,
            "importe": 5000.0,
            "cuenta_pgp": ""
          }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {
          "generation_datetime": "2024-11-08T15:30:00.000Z"
        }
      }
    }
  }
}
```

#### Field Descriptions

**Top-level fields:**
- `task_id`: Unique task identifier (used for tracking and logging)
- `operation_data`: Container object for operation details
  - `operation`: Operation object containing type and details
    - `tipo`: Operation type identifier (read from message, typically "arqueo")
    - `detalle`: Detailed operation data (see below)

**Detalle fields (inside operation_data.operation.detalle):**
- `fecha`: Date in format `ddmmyyyy` (e.g., "08112024")
- `caja`: Cash register code
- `expediente`: Expedition code (empty string or code)
- `tercero`: Third-party identifier (NIF/CIF)
- `naturaleza`: Operation nature ("4" for expenses, "5" for income)
- `texto_sical`: Array with operation description
  - `tcargo`: Operation description text
- `aplicaciones`: Array of budget line applications (NEW structure)
  - `year`: 4-digit year (e.g., "2024")
  - `economica`: Budget line code (e.g., "30012")
  - `proyecto`: Project code (empty or project number)
  - `contraido`: Committed status (boolean `true`/`false` or 7-digit integer)
  - `base_imponible`: Taxable base (float, default 0.0)
  - `tipo`: Rate/type (float, default 0.0)
  - `importe`: Amount (float)
  - `cuenta_pgp`: PGP account code (empty or code)
- `descuentos`: Array of discounts (usually empty)
- `aux_data`: Auxiliary data object (usually empty)
- `metadata`: Metadata object with generation info

**Note**: The old `final` array with `partida` and `IMPORTE_PARTIDA` fields is **no longer supported**. Use the new `aplicaciones` structure.

### Response Format

The robot sends responses to the `sical_results` queue:

```json
{
  "status": "COMPLETED",
  "operation_id": "unique-task-id",
  "result": {
    "status": "COMPLETED",
    "init_time": "2024-12-01 10:00:00",
    "end_time": "2024-12-01 10:05:00",
    "duration": "0:05:00",
    "num_operacion": "12345",
    "total_operacion": 351.25,
    "suma_aplicaciones": 351.25,
    "sical_is_open": false,
    "error": null
  }
}
```

### Message Examples

#### Example 1: Multiple Aplicaciones

```json
{
  "task_id": "207_08112024_1400_expense",
  "operation_data": {
    "operation": {
      "tipo": "arqueo",
      "detalle": {
        "fecha": "08112024",
        "caja": "207",
        "expediente": "",
        "tercero": "000",
        "naturaleza": "4",
        "texto_sical": [{"tcargo": "TRANSF. N/F: LICENCIA DE OBRA"}],
        "aplicaciones": [
          {
            "year": "2024",
            "economica": "290",
            "proyecto": "",
            "contraido": false,
            "base_imponible": 0.0,
            "tipo": 0.0,
            "importe": 1200.0,
            "cuenta_pgp": ""
          },
          {
            "year": "2024",
            "economica": "20104",
            "proyecto": "",
            "contraido": true,
            "base_imponible": 0.0,
            "tipo": 0.0,
            "importe": 200.0,
            "cuenta_pgp": ""
          }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {"generation_datetime": "2024-11-08T15:30:00.000Z"}
      }
    }
  }
}
```

#### Example 2: Arqueo with Proyecto

```json
{
  "task_id": "207_08112024_1500_project",
  "operation_data": {
    "operation": {
      "tipo": "arqueo",
      "detalle": {
        "fecha": "08112024",
        "caja": "207",
        "expediente": "",
        "tercero": "45575500B",
        "naturaleza": "4",
        "texto_sical": [{"tcargo": "TRANSF N/F SUBVENCION GUARDERIA"}],
        "aplicaciones": [
          {
            "year": "2024",
            "economica": "45002",
            "proyecto": "24000014",
            "contraido": false,
            "base_imponible": 0.0,
            "tipo": 0.0,
            "importe": 1500.0,
            "cuenta_pgp": ""
          }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {"generation_datetime": "2024-11-08T15:30:00.000Z"}
      }
    }
  }
}
```

#### Example 3: Contraido with Numeric Value

```json
{
  "task_id": "203_08112024_50_income",
  "operation_data": {
    "operation": {
      "tipo": "arqueo",
      "detalle": {
        "fecha": "08112024",
        "caja": "203",
        "expediente": "",
        "tercero": "25352229L",
        "naturaleza": "5",
        "texto_sical": [{"tcargo": "FRACCIONAMIENTO DEUDA"}],
        "aplicaciones": [
          {
            "year": "2024",
            "economica": "39900",
            "proyecto": "",
            "contraido": 2500046,
            "base_imponible": 0.0,
            "tipo": 0.0,
            "importe": 50.0,
            "cuenta_pgp": ""
          }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {"generation_datetime": "2024-11-08T15:30:00.000Z"}
      }
    }
  }
}
```

### Operation Status Values

- `PENDING` - Operation queued but not started
- `IN_PROGRESS` - Currently processing
- `COMPLETED` - Successfully completed
- `INCOMPLETED` - Partially completed with warnings
- `FAILED` - Operation failed with errors

### Migration from Old Format

**⚠️ Breaking Change**: The consumer **no longer supports** the old message format.

**Old Format (DEPRECATED - Not Supported)**:
```json
{
  "final": [
    {
      "partida": "30012",
      "contraido": "True",
      "IMPORTE_PARTIDA": 5000.0
    },
    {
      "partida": "Total",
      "IMPORTE_PARTIDA": 0.0
    }
  ]
}
```

**Field Migration Mapping**:
| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `final` | `aplicaciones` | Array renamed |
| `partida` | `economica` | Budget line code |
| `IMPORTE_PARTIDA` | `importe` | Amount (float, not string) |
| `contraido: "True"/"False"` | `contraido` | Now boolean or integer |
| N/A | `year` | NEW: 4-digit year |
| N/A | `proyecto` | NEW: Project code |
| N/A | `base_imponible` | NEW: Taxable base |
| N/A | `tipo` | NEW: Rate/type |
| N/A | `cuenta_pgp` | NEW: PGP account |
| N/A | `expediente` | NEW: Expedition code |
| N/A | `descuentos` | NEW: Discounts array |
| N/A | `aux_data` | NEW: Auxiliary data |
| N/A | `metadata` | NEW: Generation metadata |

**Important Changes**:
- ✅ Use `task_id` field (not `id_task`)
- ✅ Wrap operation in `operation_data.operation` structure
- ✅ Use `aplicaciones` array (not `final`)
- ✅ Use `economica` field (not `partida`)
- ✅ Use `importe` as float (not `IMPORTE_PARTIDA` as string)
- ✅ Use `contraido` as boolean or integer (not string "True"/"False")
- ✅ No "Total" rows in new structure
- ✅ Response queue is now `sical_results` (not `reply_to`)

For detailed migration information, see [docs/MIGRATION_VERIFICATION_REPORT.md](docs/MIGRATION_VERIFICATION_REPORT.md) and [docs/RESULT_QUEUE_CHANGE.md](docs/RESULT_QUEUE_CHANGE.md).

## GUI Status Monitor

The robot includes a comprehensive GUI for real-time monitoring and historical task analysis. The GUI provides a user-friendly interface for managing the service, viewing task progress, and analyzing historical data.

### GUI Features

- 📊 **Real-time Monitoring** - Live service status and task progress
- 📜 **Complete Task History** - SQLite-based persistent storage from day zero
- 🔍 **Search & Filter** - Find tasks by ID, operation, third party, or status
- 📤 **Export Capabilities** - Export history to Excel, JSON, or CSV
- 📈 **Statistics Dashboard** - Overall metrics and success rates
- 🎯 **Detailed Task View** - Complete task information on double-click

### Running the GUI

#### Standard Launch

```bash
# Using the main GUI script
python arqueos_gui.py

# Or using the convenience launcher
python run_gui.py
```

The GUI window will open automatically. From there, you can:
1. Click **"▶ Start Service"** to begin processing tasks
2. Monitor real-time task execution in the Monitor tab
3. View historical tasks in the History tab
4. Stop the service with **"⏹ Stop Service"**

### GUI Architecture

The GUI uses a **minimal wrapper approach** with callback hooks:
- **Non-invasive**: Only ~60 lines added to existing code
- **Thread-safe**: Separate GUI and worker threads with proper synchronization
- **Status Manager**: Centralized state management singleton
- **Database Persistence**: Automatic SQLite logging of all tasks

### GUI Tabs

#### 📊 Monitor Tab

Real-time monitoring of the robot service:

**Service Status Panel:**
- Service running/stopped indicator
- RabbitMQ connection status
- Session uptime counter

**Statistics Panel:**
- Pending tasks count
- Currently processing count
- Completed tasks count
- Failed tasks count
- Success rate percentage

**Current Task Panel:**
Shows detailed information about the task being processed:
- Task ID and operation number
- Date, cash register, third party
- Operation type (Income/Expenses)
- Amount and description
- Line items progress with percentage
- Current processing step

**Activity Log:**
- Real-time log messages with color coding
- INFO (black), WARNING (orange), ERROR (red), DEBUG (gray)
- Automatic scrolling to latest messages
- Last 50 messages displayed

**Control Buttons:**
- Start Service: Begin processing tasks from queue
- Stop Service: Gracefully stop the consumer
- Clear Stats: Reset session statistics

#### 📜 History Tab

Complete historical task database with search and export:

**Search & Filter Panel:**
- Search box: Find by task ID, operation, or third party
- Status filter: All / Completed / Failed / Error
- Refresh button: Reload latest data

**Overall Statistics:**
- Total tasks processed since day zero
- Completed count (green)
- Failed count (red)
- Average task duration

**Task History Table:**
Sortable table with the following columns:
- Task ID
- Date
- Operation Number
- Amount
- Cash Register
- Third Party
- Type (Income/Expenses)
- Status (color-coded)
- Duration (mm:ss)
- Completed At

**Features:**
- Most recent tasks displayed first
- Color-coded rows (green=completed, red=failed)
- Double-click any row to view full details
- Horizontal and vertical scrolling

**Task Details Window:**
Double-clicking a row opens a popup with complete task information:
- Task identification (ID, operation number, status)
- Operation details (date, cash register, third party, nature, amount, description)
- Timing information (started at, completed at, duration)
- Error messages (if task failed)
- All data formatted for easy reading

**Export Panel:**
Export complete history to various formats:
- **📊 Excel (.xlsx)**: Formatted spreadsheet with headers and auto-sized columns
- **📄 JSON**: Machine-readable format for data processing
- **📋 CSV**: Comma-separated values for spreadsheet import

### Database Persistence

The GUI automatically maintains a complete audit trail:

**Database File:** `arqueos_history.db` (created automatically)

**Stored Information:**
- Task ID, operation number, amount
- Date, cash register, third party, nature
- Description and line item count
- Status (completed/failed/error)
- Start time, completion time, duration
- Error messages for failed tasks
- Raw data backup (JSON)

**Benefits:**
- ✅ Zero-configuration persistence
- ✅ Data survives service restarts
- ✅ Complete audit trail from day zero
- ✅ Fast search and retrieval
- ✅ Easy backup (single file)
- ✅ No external database server required

**Backup Strategy:**
Simply copy `arqueos_history.db` to backup location:
```bash
# Backup database
cp arqueos_history.db backups/arqueos_history_$(date +%Y%m%d).db

# Restore from backup
cp backups/arqueos_history_20241213.db arqueos_history.db
```

### Export Functionality

#### Excel Export

Creates a formatted `.xlsx` file with:
- Header row with bold formatting
- Auto-sized columns
- All task details
- Professional appearance

**Requirements:**
```bash
pip install openpyxl
```

**Usage:**
1. Go to History tab
2. Click **"📊 Excel (.xlsx)"**
3. Choose save location
4. Open in Excel, LibreOffice, or Google Sheets

#### JSON Export

Creates a machine-readable JSON file:
- Array of task objects
- ISO 8601 timestamps
- Suitable for data processing scripts
- Can be imported into other systems

**No additional dependencies required.**

#### CSV Export

Creates a comma-separated values file:
- Compatible with all spreadsheet applications
- Can be imported into databases
- Simple text format

**No additional dependencies required.**

### GUI Requirements

**Core Requirements (included in requirements.txt):**
- `tkinter` - GUI framework (included with Python)
- `sqlite3` - Database (included with Python)

**Optional Requirements:**
```bash
# For Excel export functionality
pip install openpyxl
```

**Note:** JSON and CSV export work without additional dependencies.

### Packaging for Distribution

The GUI can be packaged as a standalone Windows executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Create standalone executable
pyinstaller --onefile --windowed --name="ArqueosRobot" arqueos_gui.py

# Executable will be in dist/ArqueosRobot.exe
```

**Advantages for distribution:**
- Single `.exe` file - no Python installation required
- Professional Windows application
- Includes all dependencies
- Easy deployment to municipal staff
- No command-line knowledge needed

### GUI Files

The GUI implementation consists of:
- `arqueos_gui.py` (1,100+ lines) - Main GUI application with tabbed interface
- `status_manager.py` (260 lines) - Thread-safe state manager with DB persistence
- `task_history_db.py` (400+ lines) - SQLite database manager with export functions
- `run_gui.py` (10 lines) - Convenience launcher script

### Troubleshooting GUI

**GUI doesn't show task data:**
- Check that SICAL application is running
- Verify tasks are being received from RabbitMQ
- Check Activity Log for error messages

**History tab is empty:**
- Click "🔄 Refresh" button
- Ensure tasks have been processed (check Monitor tab first)
- Database file `arqueos_history.db` should exist in project root

**Excel export fails:**
- Install openpyxl: `pip install openpyxl`
- Use JSON or CSV export as alternative

**Service won't start:**
- Check RabbitMQ connection settings in `.env`
- Verify RabbitMQ server is running
- Check Activity Log for connection errors

## Project Structure

```
arqueos_robot/
├── main.py                      # Entry point (CLI mode)
├── arqueo_tasks.py              # Core business logic (559 lines)
├── arqueo_task_consumer.py      # RabbitMQ consumer (170 lines)
├── config.py                    # Configuration management
├── arqueos_gui.py               # GUI application (1,100+ lines)
├── status_manager.py            # Thread-safe state manager (260 lines)
├── task_history_db.py           # SQLite database manager (400+ lines)
├── run_gui.py                   # GUI launcher
├── arqueos_history.db           # Task history database (auto-created)
├── requirements.txt             # Python dependencies
├── conda.yaml                   # Conda environment specification
├── robot.yaml                   # Robocorp configuration
├── pytest.ini                   # Pytest configuration
├── .coveragerc                  # Coverage configuration
├── .env.example                 # Example environment variables
├── .gitignore                   # Git ignore patterns
├── README.md                    # This file
├── docs/                        # Documentation
│   ├── TESTING.md               # Testing documentation
│   ├── MIGRATION_VERIFICATION_REPORT.md  # Migration verification
│   └── RESULT_QUEUE_CHANGE.md   # Result queue documentation
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── conftest.py              # Shared test fixtures
│   ├── test_arqueo_tasks.py     # Business logic tests
│   ├── test_arqueo_task_consumer.py  # Consumer tests
│   ├── test_config.py           # Configuration tests
│   ├── test_migration.py        # Migration tests
│   ├── test_exact_structure.py  # Structure validation tests
│   ├── test_result_queue.py     # Result queue tests
│   └── verify_new_structure.py  # Comprehensive verification
├── .github/
│   └── workflows/
│       └── test.yml             # CI/CD pipeline
└── data/                        # Data directories (created at runtime)
    ├── pending/
    ├── processed/
    └── z_failed/
```

## Testing

### Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Test Coverage

The project has comprehensive test coverage:
- ✅ Data transformation functions
- ✅ RabbitMQ message handling
- ✅ Operation result handling
- ✅ Configuration management
- ✅ Error handling

For detailed testing information, see [TESTING.md](docs/TESTING.md).

## Configuration

### Partida Mapping

The robot uses a hardcoded mapping (`partidas_cuentaPG`) for Spanish municipal accounting codes:

| Partida | Cuenta PG | Description |
|---------|-----------|-------------|
| 130 | 727 | IAE (Tax on Economic Activities) |
| 300 | 740 | Water supply service |
| 302 | 740 | Garbage service |
| 332 | 742 | TOPV utility companies |
| 42000 | 7501 | State tax participation |
| ... | ... | (See arqueo_tasks.py:21-40) |

### Data Directories

The robot expects the following directories (created automatically):
- `data/pending/` - Pending operations
- `data/processed/` - Successfully completed operations
- `data/z_failed/` - Failed operations

## Development

### Running in Development Mode

```bash
# Activate virtual environment
source venv/bin/activate  # or conda activate arqueos

# Run with debug logging
python main.py
```

### Code Style

The project follows Python best practices:
- Type hints for better code clarity
- Dataclasses for structured data
- Enum for type-safe status values
- Comprehensive error handling

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Continuous Integration

The project uses GitHub Actions for CI/CD:
- ✅ Automated testing on Python 3.10 and 3.11
- ✅ Code coverage reporting
- ✅ Linting with flake8, black, isort
- ✅ Test artifacts and coverage reports

## Troubleshooting

### SICAL Window Not Found

**Error**: `Failed to open SICAL window`

**Solution**:
- Ensure SICAL II 4.2 is running
- Check the window title matches `.*SICAL II 4.2 mtec40`
- Verify Windows UI automation permissions

### RabbitMQ Connection Failed

**Error**: `Failed to connect to RabbitMQ`

**Solution**:
- Check RabbitMQ server is running
- Verify connection parameters in `.env`
- Test connection: `telnet localhost 5672`

### Import Errors

**Error**: `ModuleNotFoundError`

**Solution**:
```bash
pip install -r requirements.txt
```

## Architecture

### Message Flow

```
External Service
    ↓
RabbitMQ Queue (sical_queue.arqueo)
    ↓
ArqueoConsumer.callback()
    ↓
operacion_arqueo() task
    ↓
SICAL II Window Automation
    ↓
OperationResult
    ↓
RabbitMQ Reply Queue
    ↓
External Service
```

### Key Components

1. **ArqueoConsumer** - RabbitMQ message consumer
2. **operacion_arqueo()** - Main task orchestrator
3. **SicalWindowManager** - SICAL window lifecycle manager
4. **OperationResult** - Result encapsulation
5. **Data Transformers** - Message to SICAL format conversion

## Known Limitations

- ⚠️ Windows-only (SICAL II requirement)
- ⚠️ Validation function not yet implemented (commented out)
- ⚠️ Print document function incomplete
- ⚠️ Window cleanup disabled during development

## Roadmap

- [x] ~~Add file-based audit trail~~ **COMPLETED** (SQLite database with GUI)
- [x] ~~Implement monitoring/metrics~~ **COMPLETED** (GUI status monitor)
- [ ] Complete validation implementation
- [ ] Implement document printing
- [ ] Extract hardcoded partida mapping to config file
- [ ] Add Docker support
- [ ] Add retry mechanisms for transient failures
- [ ] Add automated report generation from history database

## License

[Specify your license here]

## Authors

- **AALVAREZG** - Initial work

## Acknowledgments

- Robocorp for the RPA framework
- SICAL II system documentation
- Spanish municipal finance community

## Support

For issues, questions, or contributions:
- Create an issue: https://github.com/AALVAREZG/arqueos_robot/issues
- Documentation: See [TESTING.md](docs/TESTING.md)

---

**Version**: 2.0 (GUI Release)
**Last Updated**: December 2024

## Changelog

### Version 2.0 - GUI Release (December 2024)
- ✨ Added comprehensive GUI with tabbed interface (Monitor + History)
- 📊 Real-time task monitoring with detailed progress tracking
- 📜 Complete task history with SQLite database persistence
- 🔍 Search and filter capabilities for historical tasks
- 📤 Export functionality (Excel, JSON, CSV)
- 📈 Statistics dashboard with success rates and metrics
- 🎯 Detailed task view with double-click popup
- 🗄️ Zero-configuration SQLite database for audit trail
- 🧵 Thread-safe architecture with callback hooks
- 🐛 Fixed task detail formatting errors with None values

### Version 1.5 (November 2024)
- Updated message format to new structure with `aplicaciones`
- Deprecated old `final` array format
- Improved error handling and logging
