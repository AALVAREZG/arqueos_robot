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
  "id_task": "204_08112024_5000_MPTOST",
  "num_operaciones": 1,
  "liquido_operaciones": 5000.0,
  "creation_date": "2024-11-08T15:30:00.000Z",
  "operaciones": [
    {
      "tipo": "arqueo",
      "detalle": {
        "fecha": "08112024",
        "caja": "204",
        "expediente": "",
        "tercero": "43000000M",
        "texto_sical": [
          {
            "tcargo": "RECAUDADO TRIBUTOS VARIOS C60"
          }
        ],
        "naturaleza": "5",
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
  ]
}
```

#### Field Descriptions

**Top-level fields:**
- `id_task`: Unique task identifier
- `num_operaciones`: Number of operations in this task
- `liquido_operaciones`: Total liquid amount
- `creation_date`: Task creation timestamp (ISO 8601)
- `operaciones`: Array of operations to process

**Operation detalle fields:**
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
  "tipo": "arqueo",
  "detalle": {
    "fecha": "08112024",
    "caja": "207",
    "expediente": "",
    "tercero": "000",
    "texto_sical": [{"tcargo": "TRANSF. N/F: LICENCIA DE OBRA"}],
    "naturaleza": "4",
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
```

#### Example 2: Arqueo with Proyecto

```json
{
  "tipo": "arqueo",
  "detalle": {
    "fecha": "08112024",
    "caja": "207",
    "expediente": "",
    "tercero": "45575500B",
    "texto_sical": [{"tcargo": "TRANSF N/F SUBVENCION GUARDERIA"}],
    "naturaleza": "4",
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
```

#### Example 3: Contraido with Numeric Value

```json
{
  "tipo": "arqueo",
  "detalle": {
    "fecha": "08112024",
    "caja": "203",
    "expediente": "",
    "tercero": "25352229L",
    "texto_sical": [{"tcargo": "FRACCIONAMIENTO DEUDA"}],
    "naturaleza": "5",
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
- ✅ Use `aplicaciones` array (not `final`)
- ✅ Use `economica` field (not `partida`)
- ✅ Use `importe` as float (not `IMPORTE_PARTIDA` as string)
- ✅ Use `contraido` as boolean or integer (not string "True"/"False")
- ✅ No "Total" rows in new structure
- ✅ Response queue is now `sical_results` (not `reply_to`)

For detailed migration information, see [docs/MIGRATION_VERIFICATION_REPORT.md](docs/MIGRATION_VERIFICATION_REPORT.md) and [docs/RESULT_QUEUE_CHANGE.md](docs/RESULT_QUEUE_CHANGE.md).

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
