"""
Unit tests for arqueo_task_consumer.py module.

Tests cover:
- ArqueoConsumer initialization
- RabbitMQ connection setup
- Message callback processing
- Error handling
"""

import pytest
import json
import pika
from unittest.mock import Mock, MagicMock, patch, call
from arqueo_task_consumer import ArqueoConsumer
from arqueo_tasks import OperationResult, OperationStatus


class TestArqueoConsumerInit:
    """Tests for ArqueoConsumer initialization."""

    @pytest.mark.integration
    def test_consumer_initialization(self, mock_rabbitmq_connection):
        """Test that consumer initializes with correct queue name."""
        consumer = ArqueoConsumer()

        assert consumer.queue_name == 'sical_queue.arqueo'
        assert consumer.connection is not None
        assert consumer.channel is not None

    @pytest.mark.integration
    def test_connection_failure_raises_exception(self, mocker):
        """Test that connection failure raises an exception."""
        # Mock pika to raise exception
        mocker.patch('pika.BlockingConnection', side_effect=Exception("Connection failed"))

        with pytest.raises(Exception, match="Connection failed"):
            ArqueoConsumer()


class TestSetupConnection:
    """Tests for the setup_connection method."""

    @pytest.mark.integration
    def test_connection_parameters(self, mocker):
        """Test that connection is created with correct parameters."""
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        mock_connection.channel.return_value = mock_channel

        mock_blocking_connection = mocker.patch(
            'pika.BlockingConnection',
            return_value=mock_connection
        )
        mock_credentials = mocker.patch('pika.PlainCredentials')

        consumer = ArqueoConsumer()

        # Verify credentials were created
        mock_credentials.assert_called_once()

        # Verify connection was established
        mock_blocking_connection.assert_called_once()

        # Verify channel setup
        assert consumer.channel == mock_channel

    @pytest.mark.integration
    def test_queue_declaration(self, mock_rabbitmq_connection):
        """Test that queue is declared as durable."""
        consumer = ArqueoConsumer()

        # Verify queue was declared with correct parameters
        consumer.channel.queue_declare.assert_called_with(
            queue='sical_queue.arqueo',
            durable=True
        )

    @pytest.mark.integration
    def test_qos_configuration(self, mock_rabbitmq_connection):
        """Test that QoS is set to process one message at a time."""
        consumer = ArqueoConsumer()

        # Verify QoS was configured
        consumer.channel.basic_qos.assert_called_with(prefetch_count=1)


class TestCallback:
    """Tests for the callback message processing method."""

    @pytest.mark.integration
    def test_successful_message_processing(
        self,
        mock_rabbitmq_connection,
        sample_rabbitmq_message,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test successful processing of a valid message."""
        consumer = ArqueoConsumer()

        # Mock the operacion_arqueo task to return a successful result
        mock_result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-12-01 10:00:00",
            end_time="2024-12-01 10:05:00",
            duration="0:05:00",
            num_operacion="12345"
        )

        mocker.patch('arqueo_task_consumer.operacion_arqueo', return_value=mock_result)

        # Process the message
        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            sample_rabbitmq_message
        )

        # Verify message was acknowledged
        consumer.channel.basic_ack.assert_called_once_with(
            delivery_tag=mock_rabbitmq_method.delivery_tag
        )

        # Verify response was published
        consumer.channel.basic_publish.assert_called_once()
        publish_call = consumer.channel.basic_publish.call_args

        assert publish_call[1]['routing_key'] == mock_rabbitmq_properties.reply_to
        assert publish_call[1]['properties'].correlation_id == mock_rabbitmq_properties.correlation_id

    @pytest.mark.integration
    def test_message_parsing(
        self,
        mock_rabbitmq_connection,
        sample_rabbitmq_message,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test that message body is correctly parsed."""
        consumer = ArqueoConsumer()

        # Mock operacion_arqueo to capture the data it receives
        mock_operacion = mocker.patch('arqueo_task_consumer.operacion_arqueo')
        mock_operacion.return_value = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-12-01 10:00:00"
        )

        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            sample_rabbitmq_message
        )

        # Verify operacion_arqueo was called with correct data
        mock_operacion.assert_called_once()
        call_args = mock_operacion.call_args[0][0]

        assert 'fecha' in call_args
        assert call_args['fecha'] == '01/12/2024'

    @pytest.mark.integration
    def test_response_structure(
        self,
        mock_rabbitmq_connection,
        sample_rabbitmq_message,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test that response has correct structure."""
        consumer = ArqueoConsumer()

        mock_result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-12-01 10:00:00"
        )

        mocker.patch('arqueo_task_consumer.operacion_arqueo', return_value=mock_result)

        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            sample_rabbitmq_message
        )

        # Get the response body that was published
        publish_call = consumer.channel.basic_publish.call_args
        response_body = publish_call[1]['body']
        response = json.loads(response_body)

        # Verify response structure
        assert 'status' in response
        assert 'operation_id' in response
        assert 'result' in response
        assert response['status'] == 'COMPLETED'
        assert response['operation_id'] == 'task-12345'

    @pytest.mark.integration
    def test_failed_operation_handling(
        self,
        mock_rabbitmq_connection,
        sample_rabbitmq_message,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test handling of failed operations."""
        consumer = ArqueoConsumer()

        mock_result = OperationResult(
            status=OperationStatus.FAILED,
            init_time="2024-12-01 10:00:00",
            error="SICAL window not found"
        )

        mocker.patch('arqueo_task_consumer.operacion_arqueo', return_value=mock_result)

        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            sample_rabbitmq_message
        )

        # Should still acknowledge the message
        consumer.channel.basic_ack.assert_called_once()

        # Response should contain error
        publish_call = consumer.channel.basic_publish.call_args
        response_body = publish_call[1]['body']
        response = json.loads(response_body)

        assert response['status'] == 'FAILED'
        assert response['result']['error'] == 'SICAL window not found'

    @pytest.mark.integration
    def test_exception_handling_with_nack(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test that exceptions trigger negative acknowledgment."""
        consumer = ArqueoConsumer()

        # Simulate an exception during processing
        mocker.patch(
            'arqueo_task_consumer.operacion_arqueo',
            side_effect=Exception("Processing error")
        )

        invalid_message = b'invalid json'

        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            invalid_message
        )

        # Should send negative acknowledgment
        consumer.channel.basic_nack.assert_called_once_with(
            delivery_tag=mock_rabbitmq_method.delivery_tag
        )

        # Should NOT acknowledge
        consumer.channel.basic_ack.assert_not_called()

    @pytest.mark.integration
    def test_invalid_json_handling(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_properties,
        mock_rabbitmq_method
    ):
        """Test handling of invalid JSON in message."""
        consumer = ArqueoConsumer()

        invalid_message = b'not valid json {'

        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            invalid_message
        )

        # Should send negative acknowledgment
        consumer.channel.basic_nack.assert_called_once()


class TestStartConsuming:
    """Tests for the start_consuming method."""

    @pytest.mark.integration
    def test_consumer_registration(self, mock_rabbitmq_connection):
        """Test that consumer is registered with correct parameters."""
        consumer = ArqueoConsumer()

        # Mock start_consuming to avoid blocking
        consumer.channel.start_consuming = Mock()

        consumer.start_consuming()

        # Verify basic_consume was called
        consumer.channel.basic_consume.assert_called_once_with(
            queue='sical_queue.arqueo',
            on_message_callback=consumer.callback
        )

        # Verify start_consuming was called
        consumer.channel.start_consuming.assert_called_once()

    @pytest.mark.integration
    def test_keyboard_interrupt_handling(self, mock_rabbitmq_connection, mocker):
        """Test graceful shutdown on keyboard interrupt."""
        consumer = ArqueoConsumer()

        # Mock start_consuming to raise KeyboardInterrupt
        consumer.channel.start_consuming = Mock(side_effect=KeyboardInterrupt())

        # Mock stop_consuming
        mock_stop = mocker.patch.object(consumer, 'stop_consuming')

        consumer.start_consuming()

        # Verify stop_consuming was called
        mock_stop.assert_called_once()

    @pytest.mark.integration
    def test_exception_during_consuming(self, mock_rabbitmq_connection, mocker):
        """Test exception handling during message consumption."""
        consumer = ArqueoConsumer()

        # Mock start_consuming to raise exception
        consumer.channel.start_consuming = Mock(
            side_effect=Exception("Connection lost")
        )

        # Mock stop_consuming
        mock_stop = mocker.patch.object(consumer, 'stop_consuming')

        with pytest.raises(Exception, match="Connection lost"):
            consumer.start_consuming()

        # Verify stop_consuming was called
        mock_stop.assert_called_once()


class TestStopConsuming:
    """Tests for the stop_consuming method."""

    @pytest.mark.integration
    def test_graceful_shutdown(self, mock_rabbitmq_connection):
        """Test graceful shutdown of consumer."""
        consumer = ArqueoConsumer()

        consumer.stop_consuming()

        # Verify channel stop_consuming was called
        consumer.channel.stop_consuming.assert_called_once()

        # Verify connection was closed
        consumer.connection.close.assert_called_once()

    @pytest.mark.integration
    def test_stop_with_no_channel(self, mock_rabbitmq_connection):
        """Test stop_consuming when channel is None."""
        consumer = ArqueoConsumer()
        consumer.channel = None

        # Should not raise exception
        consumer.stop_consuming()

        # Connection should still be closed
        consumer.connection.close.assert_called_once()

    @pytest.mark.integration
    def test_stop_with_closed_connection(self, mock_rabbitmq_connection):
        """Test stop_consuming when connection is already closed."""
        consumer = ArqueoConsumer()
        consumer.connection.is_closed = True

        consumer.stop_consuming()

        # Channel should stop consuming
        consumer.channel.stop_consuming.assert_called_once()

        # Connection close should not be called
        consumer.connection.close.assert_not_called()

    @pytest.mark.integration
    def test_exception_during_shutdown(self, mock_rabbitmq_connection):
        """Test that exceptions during shutdown are handled."""
        consumer = ArqueoConsumer()

        # Mock channel to raise exception
        consumer.channel.stop_consuming = Mock(side_effect=Exception("Error"))

        # Should not raise exception
        consumer.stop_consuming()


class TestIntegration:
    """Integration tests for complete message flow."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_complete_message_flow(
        self,
        mock_rabbitmq_connection,
        sample_rabbitmq_message,
        mock_rabbitmq_properties,
        mock_rabbitmq_method,
        mocker
    ):
        """Test complete flow from message receipt to response."""
        # Setup consumer
        consumer = ArqueoConsumer()

        # Mock operacion_arqueo
        mock_result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-12-01 10:00:00",
            end_time="2024-12-01 10:05:00",
            duration="0:05:00",
            num_operacion="OPR-12345",
            total_operacion=851.25,
            suma_aplicaciones=851.25,
            sical_is_open=False
        )
        mocker.patch('arqueo_task_consumer.operacion_arqueo', return_value=mock_result)

        # Process message
        consumer.callback(
            consumer.channel,
            mock_rabbitmq_method,
            mock_rabbitmq_properties,
            sample_rabbitmq_message
        )

        # Verify complete flow
        # 1. Message was parsed
        # 2. Operation was executed
        # 3. Response was published
        publish_call = consumer.channel.basic_publish.call_args
        response = json.loads(publish_call[1]['body'])

        assert response['status'] == 'COMPLETED'
        assert response['result']['num_operacion'] == 'OPR-12345'
        assert response['result']['total_operacion'] == 851.25

        # 4. Message was acknowledged
        consumer.channel.basic_ack.assert_called_once()
