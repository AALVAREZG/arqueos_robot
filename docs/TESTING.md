# Testing Documentation

This document provides comprehensive information about the testing infrastructure for the Arqueos Robot project.

## Overview

The project uses **pytest** as the testing framework with comprehensive test coverage for:
- Data transformation functions
- RabbitMQ message handling
- Operation result handling
- Configuration management

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared fixtures and test configuration
├── test_arqueo_tasks.py     # Tests for business logic and data transformations
├── test_arqueo_task_consumer.py  # Tests for RabbitMQ consumer
└── test_config.py           # Tests for configuration module
```

## Prerequisites

Install testing dependencies:

```bash
pip install -r requirements.txt
```

The testing dependencies include:
- `pytest==7.4.3` - Testing framework
- `pytest-mock==3.12.0` - Mocking support
- `pytest-cov==4.1.0` - Coverage reporting
- `pytest-timeout==2.2.0` - Timeout handling for tests

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_arqueo_tasks.py
pytest tests/test_arqueo_task_consumer.py
pytest tests/test_config.py
```

### Run Specific Test Class or Function

```bash
# Run a specific test class
pytest tests/test_arqueo_tasks.py::TestCleanValue

# Run a specific test function
pytest tests/test_arqueo_tasks.py::TestCleanValue::test_boolean_true_unchanged
```

### Run Tests by Marker

Tests are organized using markers for easy filtering:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run slow tests
pytest -m slow

# Exclude slow tests
pytest -m "not slow"
```

Available markers:
- `unit` - Unit tests for individual functions
- `integration` - Integration tests with external services
- `slow` - Tests that take longer to run
- `windows` - Tests that require Windows UI automation

## Coverage Reports

### Generate Coverage Report

```bash
# Terminal output with missing lines
pytest --cov=. --cov-report=term-missing

# HTML report
pytest --cov=. --cov-report=html

# XML report (for CI/CD)
pytest --cov=. --cov-report=xml
```

### View HTML Coverage Report

After generating the HTML report:

```bash
# Open in browser (Linux/Mac)
open htmlcov/index.html

# Windows
start htmlcov/index.html
```

### Coverage Configuration

Coverage settings are configured in `.coveragerc`:
- Excludes test files, virtual environments, and output directories
- Shows missing line numbers
- Highlights uncovered code

## Test Categories

### Unit Tests (`-m unit`)

Fast, isolated tests for individual functions:
- `test_clean_value` - Tests value cleaning and type conversion
- `test_create_aplicaciones` - Tests aplicaciones data transformation
- `test_create_arqueo_data` - Tests arqueo data creation
- `test_operation_status` - Tests operation status enum
- `test_operation_result` - Tests operation result dataclass
- `test_partidas_mapping` - Tests partida to cuenta mapping

### Integration Tests (`-m integration`)

Tests that involve external dependencies (mocked):
- `test_arqueo_consumer_init` - Tests RabbitMQ consumer initialization
- `test_setup_connection` - Tests RabbitMQ connection setup
- `test_callback` - Tests message processing
- `test_start_consuming` - Tests message consumption
- `test_stop_consuming` - Tests graceful shutdown

## Fixtures

Reusable test fixtures are defined in `tests/conftest.py`:

### Data Fixtures
- `sample_operation_data` - Sample operation with naturaleza=4
- `sample_operation_data_naturaleza_5` - Sample operation with naturaleza=5
- `sample_aplicaciones` - Sample aplicaciones list
- `expected_arqueo_data` - Expected transformed arqueo data

### Mock Fixtures
- `mock_rabbitmq_connection` - Mocked RabbitMQ connection
- `mock_sical_window` - Mocked SICAL window interface
- `mock_rabbitmq_properties` - Mocked message properties
- `mock_rabbitmq_method` - Mocked message method

### Utility Fixtures
- `clean_value_test_cases` - Test cases for clean_value function
- `reset_logging` - Resets logging between tests

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py` or `*_test.py`
- Test classes: `Test*` (e.g., `TestCleanValue`)
- Test functions: `test_*` (e.g., `test_boolean_true_unchanged`)

### Example Test

```python
import pytest
from arqueo_tasks import clean_value

class TestMyFeature:
    """Tests for my feature."""

    @pytest.mark.unit
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = clean_value(True)
        assert result is True

    @pytest.mark.unit
    def test_with_fixture(self, sample_operation_data):
        """Test using a fixture."""
        assert 'fecha' in sample_operation_data
```

### Using Mocks

```python
from unittest.mock import Mock, patch

def test_with_mock(mocker):
    """Test with mocked dependency."""
    # Mock a function
    mocker.patch('module.function', return_value='mocked')

    # Mock an object
    mock_obj = Mock()
    mock_obj.method.return_value = 'result'
```

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Every push to `main`, `develop`, and `claude/**` branches
- Every pull request to `main` and `develop`

The CI pipeline:
1. Runs tests on Python 3.10 and 3.11
2. Generates coverage reports
3. Uploads coverage to Codecov
4. Archives HTML coverage reports as artifacts
5. Runs linting checks (flake8, black, isort)

## Best Practices

### 1. Write Tests First (TDD)
Consider writing tests before implementing new features.

### 2. Keep Tests Independent
Each test should be able to run independently without relying on other tests.

### 3. Use Fixtures
Leverage fixtures for common setup and test data.

### 4. Mock External Dependencies
Mock RabbitMQ, SICAL windows, and other external systems.

### 5. Add Markers
Tag tests appropriately (`@pytest.mark.unit`, `@pytest.mark.integration`).

### 6. Document Tests
Add docstrings to test classes and functions explaining what they test.

### 7. Check Coverage
Aim for >80% code coverage, focusing on critical business logic.

## Troubleshooting

### Tests Fail Due to Import Errors

Ensure you're running tests from the project root:

```bash
cd /path/to/arqueos_robot
pytest
```

### RabbitMQ Connection Tests Fail

Integration tests mock RabbitMQ. If tests fail, check that:
- `pytest-mock` is installed
- Mocks are properly configured in `conftest.py`

### Coverage Report Not Generated

Ensure `pytest-cov` is installed:

```bash
pip install pytest-cov
```

### Tests Time Out

Adjust timeout in `pytest.ini`:

```ini
[pytest]
timeout = 300  # 5 minutes
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-mock documentation](https://pytest-mock.readthedocs.io/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)

## Contact

For questions about testing, please refer to the main project README or create an issue in the repository.
