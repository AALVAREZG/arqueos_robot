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
    """Fixture providing sample operation data for testing."""
    return {
        'fecha': '01/12/2024',
        'caja': '001',
        'tercero': '12345678A',
        'naturaleza': '4',
        'texto_sical': [{'tcargo': 'Test arqueo operation'}],
        'final': [
            {
                'partida': '130',
                'IMPORTE_PARTIDA': '100,50',
                'contraido': False
            },
            {
                'partida': '300',
                'IMPORTE_PARTIDA': '250,75',
                'contraido': True,
                'proyecto': 'PROJ001'
            },
            {
                'partida': '45000',
                'IMPORTE_PARTIDA': '500,00',
                'contraido': False
            },
            {
                'total': '851,25'  # This is typically the last item
            }
        ]
    }


@pytest.fixture
def sample_operation_data_naturaleza_5() -> Dict[str, Any]:
    """Fixture providing sample operation data with naturaleza=5."""
    return {
        'fecha': '15/12/2024',
        'caja': '002',
        'tercero': '87654321B',
        'naturaleza': '5',
        'texto_sical': [{'tcargo': 'Naturaleza 5 test operation'}],
        'final': [
            {
                'partida': '290',
                'IMPORTE_PARTIDA': '1500,00',
                'contraido': True
            },
            {
                'total': '1500,00'
            }
        ]
    }


@pytest.fixture
def sample_aplicaciones() -> list:
    """Fixture providing sample aplicaciones data."""
    return [
        {
            'partida': '130',
            'IMPORTE_PARTIDA': '100,50',
            'contraido': False
        },
        {
            'partida': '300',
            'IMPORTE_PARTIDA': '250,75',
            'contraido': True,
            'proyecto': 'PROJ001'
        },
        {
            'partida': '999',  # Unmapped partida
            'IMPORTE_PARTIDA': '50,00',
            'contraido': False
        },
        {
            'total': '401,25'
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
    """Fixture providing expected transformed arqueo data."""
    return {
        'fecha': '01/12/2024',
        'caja': '001',
        'expediente': 'rbt-apunte-arqueo',
        'tercero': '12345678A',
        'naturaleza': '4',
        'resumen': 'Test arqueo operation',
        'aplicaciones': [
            {
                'partida': '130',
                'importe': '100,50',
                'contraido': False,
                'proyecto': False,
                'cuenta': '727',
                'otro': False
            },
            {
                'partida': '300',
                'importe': '250,75',
                'contraido': True,
                'proyecto': 'PROJ001',
                'cuenta': '740',
                'otro': False
            },
            {
                'partida': '45000',
                'importe': '500,00',
                'contraido': False,
                'proyecto': False,
                'cuenta': '7501',
                'otro': False
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
