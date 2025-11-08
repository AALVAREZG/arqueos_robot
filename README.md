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

Run the main consumer to start listening for messages:

```bash
python main.py
```

The robot will:
1. Connect to RabbitMQ
2. Listen on the `sical_queue.arqueo` queue
3. Process incoming arqueo operations
4. Send results back to the reply queue

### Message Format

Send messages to the `sical_queue.arqueo` queue with the following structure:

```json
{
  "task_id": "unique-task-id",
  "operation_data": {
    "operation": {
      "fecha": "01/12/2024",
      "caja": "001",
      "tercero": "12345678A",
      "naturaleza": "4",
      "texto_sical": [
        {
          "tcargo": "Description of the operation"
        }
      ],
      "final": [
        {
          "partida": "130",
          "IMPORTE_PARTIDA": "100,50",
          "contraido": false
        },
        {
          "partida": "300",
          "IMPORTE_PARTIDA": "250,75",
          "contraido": true,
          "proyecto": "PROJ001"
        },
        {
          "total": "351,25"
        }
      ]
    }
  }
}
```

### Response Format

The robot sends responses to the `reply_to` queue:

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

### Operation Status Values

- `PENDING` - Operation queued but not started
- `IN_PROGRESS` - Currently processing
- `COMPLETED` - Successfully completed
- `INCOMPLETED` - Partially completed with warnings
- `FAILED` - Operation failed with errors

## Project Structure

```
arqueos_robot/
├── main.py                      # Entry point
├── arqueo_tasks.py              # Core business logic (559 lines)
├── arqueo_task_consumer.py      # RabbitMQ consumer (123 lines)
├── config.py                    # Configuration management
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
- ⚠️ No file-based audit trail implemented

## Roadmap

- [ ] Complete validation implementation
- [ ] Implement document printing
- [ ] Add file-based operation backup
- [ ] Extract hardcoded partida mapping to config file
- [ ] Add Docker support
- [ ] Implement monitoring/metrics
- [ ] Add retry mechanisms for transient failures

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

**Version**: 1.5
**Last Updated**: December 2024
