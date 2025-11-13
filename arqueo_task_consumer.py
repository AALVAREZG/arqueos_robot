# services/rabbitmq/consumer.py

import pika
import json
import dataclasses
import logging
from typing import Optional, Callable
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS
from arqueo_tasks import OperationEncoder, operacion_arqueo

logger = logging.getLogger(__name__)

# Optional status callback for GUI integration
STATUS_CALLBACK: Optional[Callable] = None


def set_status_callback(callback: Optional[Callable] = None):
    """Set the status callback function for GUI integration."""
    global STATUS_CALLBACK
    STATUS_CALLBACK = callback


class ArqueoConsumer:
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.queue_name = 'sical_queue.arqueo'
        self.setup_connection()

    def setup_connection(self):
        """Establish connection to RabbitMQ"""
        try:
            if STATUS_CALLBACK:
                STATUS_CALLBACK('connecting')

            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    retry_delay=2.0,  # Delay between connection attempts in seconds
                    socket_timeout=5.0  # Socket timeout in seconds
                )
            )
            self.channel = self.connection.channel()

            # Declare the queue we'll consume from
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True
            )

            # Declare the results queue (where we send responses)
            self.channel.queue_declare(
                queue='sical_results',
                durable=True
            )

            # Set QoS to handle one message at a time
            self.channel.basic_qos(prefetch_count=1)
            logger.info("RabbitMQ connection established successfully")

            if STATUS_CALLBACK:
                STATUS_CALLBACK('connected')

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            if STATUS_CALLBACK:
                STATUS_CALLBACK('disconnected')
            raise

    def callback(self, ch, method, properties, body):
        """
        Process incoming messages from RabbitMQ.
        This is called automatically by pika for each message received.
        """
        logger.info(f"Received message with correlation_id: {properties.correlation_id}")

        task_id = None
        try:
            # Parse the incoming message
            data = json.loads(body)
            logger.info(f"Message content: {data}")

            # DEBUG: Log to GUI
            if STATUS_CALLBACK:
                # Import here to avoid circular dependency
                from status_manager import status_manager
                status_manager.add_log(f"Received message with task_id: {data.get('task_id', 'unknown')}", "DEBUG")

                # DEBUG: Log the TOP-LEVEL keys in the message
                status_manager.add_log(f"CONSUMER: TOP-LEVEL message keys: {list(data.keys())}", "DEBUG")

                # DEBUG: Log the operation_data structure
                if 'operation_data' in data:
                    operation_data = data.get('operation_data', {})
                    status_manager.add_log(f"CONSUMER: operation_data keys: {list(operation_data.keys())}", "DEBUG")

            task_id = data.get('task_id', 'unknown')

            # Notify GUI: task received
            if STATUS_CALLBACK:
                STATUS_CALLBACK('task_received', task_id=task_id)

            # Extract operation details for GUI (with safe access)
            operation = data.get('operation_data', {}).get('operation', {})

            # The actual operation data is inside 'detalle'
            detalle = operation.get('detalle', {})

            # DEBUG: Log what we found
            if STATUS_CALLBACK:
                from status_manager import status_manager
                status_manager.add_log(f"CONSUMER: operation dict keys: {list(operation.keys())}", "DEBUG")
                status_manager.add_log(f"CONSUMER: detalle keys: {list(detalle.keys())}", "DEBUG")

            # Extract from detalle where the actual data is
            operation_number = detalle.get('num_operacion')
            total_amount = detalle.get('totalOperacion')

            # Extract additional details from detalle
            fecha = detalle.get('fecha')
            caja = detalle.get('caja')
            expediente = detalle.get('expediente', 'rbt-apunte-arqueo')
            tercero = detalle.get('tercero')
            naturaleza = detalle.get('naturaleza', '4')

            # Safely extract description from texto_sical
            resumen = None
            texto_sical = detalle.get('texto_sical', [])
            if texto_sical and len(texto_sical) > 0 and isinstance(texto_sical[0], dict):
                resumen = texto_sical[0].get('tcargo')

            aplicaciones = detalle.get('aplicaciones', [])
            total_line_items = len(aplicaciones) if aplicaciones else 0

            logger.info(f"Extracted task details - Operation: {operation_number}, Amount: {total_amount}, "
                       f"Date: {fecha}, Nature: {naturaleza}, Line items: {total_line_items}")

            # DEBUG: Log extracted details to GUI
            if STATUS_CALLBACK:
                from status_manager import status_manager
                status_manager.add_log(f"CONSUMER extracted - Operation: {operation_number}, Amount: {total_amount}, "
                                      f"Date: {fecha}, Cash: {caja}, Third Party: {tercero}, "
                                      f"Nature: {naturaleza}, Line items: {total_line_items}", "DEBUG")

            # Notify GUI: task started with full details
            if STATUS_CALLBACK:
                STATUS_CALLBACK('task_started', task_id=task_id,
                              operation_number=operation_number,
                              amount=total_amount,
                              date=fecha,
                              cash_register=caja,
                              file_reference=expediente,
                              third_party=tercero,
                              nature=naturaleza,
                              description=resumen,
                              total_line_items=total_line_items)

            # Process the arqueo operation
            result = operacion_arqueo(data['operation_data']['operation'])

            logger.info(f"RESULTADO OPERACIÓN ARQUEO.......: {result}")
            # Prepare response
            response = {
                'status': result.status.value,
                'operation_id': task_id,
                'result': dataclasses.asdict(result)
            }

            # Send response back through RabbitMQ to sical_results queue
            ch.basic_publish(
                exchange='',
                routing_key='sical_results',  # Fixed result queue
                properties=pika.BasicProperties(
                    correlation_id=properties.correlation_id
                ),

                body=json.dumps(response, cls=OperationEncoder)
            )

            # Acknowledge the message was processed successfully
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Successfully processed message {properties.correlation_id}")

            # Notify GUI: check result status to determine if completed or failed
            if STATUS_CALLBACK:
                # Check if the operation actually succeeded
                from arqueo_tasks import OperationStatus
                if result.status in (OperationStatus.COMPLETED, OperationStatus.INCOMPLETED):
                    STATUS_CALLBACK('task_completed', task_id=task_id)
                else:
                    # Operation failed (FAILED or PENDING status means something went wrong)
                    STATUS_CALLBACK('task_failed', task_id=task_id)

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            # Negative acknowledgment - message will be requeued
            ch.basic_nack(delivery_tag=method.delivery_tag)

            # Notify GUI: task failed
            if STATUS_CALLBACK and task_id:
                STATUS_CALLBACK('task_failed', task_id=task_id)

    def start_consuming(self):
        """Start consuming messages from the queue"""
        try:
            logger.info(f"Starting to consume messages from {self.queue_name}")
            
            # Register the callback function to be called when messages arrive
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.callback
            )
            
            # Start consuming messages - this blocks until stop_consuming() is called
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error while consuming messages: {e}")
            self.stop_consuming()
            raise

    def stop_consuming(self):
        """Stop consuming messages and close connections"""
        try:
            if self.channel:
                self.channel.stop_consuming()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Successfully shut down consumer")

            if STATUS_CALLBACK:
                STATUS_CALLBACK('disconnected')

        except Exception as e:
            logger.error(f"Error while shutting down: {e}")

    def start(self):
        """Convenience method to start the consumer (alias for start_consuming)"""
        self.start_consuming()

    def stop(self):
        """Convenience method to stop the consumer (alias for stop_consuming)"""
        self.stop_consuming()