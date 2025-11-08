"""
Pytest configuration and shared fixtures for testing.
"""

import pytest
import pika
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, MagicMock


@pytest.fixture
def sample_operation_data() -> Dict[str, Any]:
    """Fixture providing sample operation data for testing (NEW structure)."""
    return {
        'fecha': '01/12/2024',
        'caja': '001',
        'expediente': '',
        'tercero': '12345678A',
        'naturaleza': '4',
        'texto_sical': [{'tcargo': 'Test arqueo operation'}],
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '130',
                'proyecto': '',
                'contraido': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 100.50,
                'cuenta_pgp': ''
            },
            {
                'year': '2024',
                'economica': '300',
                'proyecto': 'PROJ001',
                'contraido': True,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 250.75,
                'cuenta_pgp': ''
            },
            {
                'year': '2024',
                'economica': '45000',
                'proyecto': '',
                'contraido': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 500.00,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-12-01T10:00:00.000Z'
        }
    }


@pytest.fixture
def sample_operation_data_naturaleza_5() -> Dict[str, Any]:
    """Fixture providing sample operation data with naturaleza=5 (NEW structure)."""
    return {
        'fecha': '15/12/2024',
        'caja': '002',
        'expediente': '',
        'tercero': '87654321B',
        'naturaleza': '5',
        'texto_sical': [{'tcargo': 'Naturaleza 5 test operation'}],
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '290',
                'proyecto': '',
                'contraido': True,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 1500.00,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-12-15T10:00:00.000Z'
        }
    }


@pytest.fixture
def sample_aplicaciones() -> list:
    """Fixture providing sample aplicaciones data (NEW structure)."""
    return [
        {
            'year': '2024',
            'economica': '130',
            'proyecto': '',
            'contraido': False,
            'base_imponible': 0.0,
            'tipo': 0.0,
            'importe': 100.50,
            'cuenta_pgp': ''
        },
        {
            'year': '2024',
            'economica': '300',
            'proyecto': 'PROJ001',
            'contraido': True,
            'base_imponible': 0.0,
            'tipo': 0.0,
            'importe': 250.75,
            'cuenta_pgp': ''
        },
        {
            'year': '2024',
            'economica': '999',  # Unmapped partida
            'proyecto': '',
            'contraido': False,
            'base_imponible': 0.0,
            'tipo': 0.0,
            'importe': 50.00,
            'cuenta_pgp': ''
        }
    ]


@pytest.fixture
def mock_rabbitmq_connection(mocker):
    """Fixture providing a mocked RabbitMQ connection."""
    mock_connection = MagicMock()
    mock_channel = MagicMock()

    # Setup the mock connection and channel
    mock_connection.channel.return_value = mock_channel
    mock_connection.is_closed = False

    # Mock pika.BlockingConnection to return our mock
    mocker.patch('pika.BlockingConnection', return_value=mock_connection)

    # Create a real PlainCredentials object instead of mocking it
    # Pika does strict type checking and rejects mocks
    real_credentials = pika.PlainCredentials('test_user', 'test_pass')
    mocker.patch('pika.PlainCredentials', return_value=real_credentials)

    return {
        'connection': mock_connection,
        'channel': mock_channel
    }


@pytest.fixture
def mock_sical_window(mocker):
    """Fixture providing a mocked SICAL window."""
    mock_window = MagicMock()
    mock_element = MagicMock()

    # Setup common window behaviors
    mock_window.find.return_value = mock_element
    mock_element.click.return_value = None
    mock_element.double_click.return_value = mock_element
    mock_element.send_keys.return_value = None
    mock_element.get_value.return_value = "100,00"
    mock_element.is_disposed.return_value = False

    # Mock the windows.find_window function
    mocker.patch('robocorp.windows.find_window', return_value=mock_window)

    return mock_window


@pytest.fixture
def mock_rabbitmq_properties():
    """Fixture providing mocked RabbitMQ message properties."""
    properties = Mock()
    properties.correlation_id = 'test-correlation-id-12345'
    properties.reply_to = 'test.reply.queue'
    return properties


@pytest.fixture
def mock_rabbitmq_method():
    """Fixture providing mocked RabbitMQ message method."""
    method = Mock()
    method.delivery_tag = 'test-delivery-tag'
    return method


@pytest.fixture
def sample_rabbitmq_message(sample_operation_data) -> bytes:
    """Fixture providing a sample RabbitMQ message body."""
    import json
    message = {
        'task_id': 'task-12345',
        'operation_data': {
            'operation': sample_operation_data
        }
    }
    return json.dumps(message).encode('utf-8')


@pytest.fixture
def expected_arqueo_data() -> Dict[str, Any]:
    """Fixture providing expected transformed arqueo data (NEW structure)."""
    return {
        'fecha': '01/12/2024',
        'caja': '001',
        'expediente': '',
        'tercero': '12345678A',
        'naturaleza': '4',
        'resumen': 'Test arqueo operation',
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-12-01T10:00:00.000Z'
        },
        'aplicaciones': [
            {
                'partida': '130',  # Internal name kept for SICAL compatibility
                'importe': '100.5',
                'contraido': False,
                'proyecto': '',
                'year': '2024',
                'cuenta': '727',
                'otro': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'cuenta_pgp': ''
            },
            {
                'partida': '300',
                'importe': '250.75',
                'contraido': True,
                'proyecto': 'PROJ001',
                'year': '2024',
                'cuenta': '740',
                'otro': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'cuenta_pgp': ''
            },
            {
                'partida': '45000',
                'importe': '500.0',
                'contraido': False,
                'proyecto': '',
                'year': '2024',
                'cuenta': '7501',
                'otro': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'cuenta_pgp': ''
            }
        ]
    }


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration between tests."""
    import logging
    # Clear existing handlers
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    yield
    # Cleanup after test
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)


@pytest.fixture
def clean_value_test_cases():
    """Fixture providing test cases for clean_value function."""
    return [
        # (input, expected_output, description)
        (True, True, "Boolean True remains True"),
        (False, False, "Boolean False remains False"),
        ('true', True, "String 'true' converts to True"),
        ('True', True, "String 'True' converts to True"),
        ('false', False, "String 'false' converts to False"),
        ('False', False, "String 'False' converts to False"),
        ('test string', 'test string', "Regular string converts to lowercase"),
        ('UPPERCASE', 'uppercase', "Uppercase string converts to lowercase"),
        (123, '123', "Integer converts to string"),
        (0, '0', "Zero converts to string '0'"),
    ]
