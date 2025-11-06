# services/rabbitmq/consumer.py

import pika
import json
import dataclasses
import logging
from typing import Optional
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS
from arqueo_tasks import OperationEncoder, operacion_arqueo

logger = logging.getLogger(__name__)


class ArqueoConsumer:
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.queue_name = 'sical_queue.arqueo'
        self.setup_connection()

    def setup_connection(self):
        """Establish connection to RabbitMQ"""
        try:
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
            
            # Set QoS to handle one message at a time
            self.channel.basic_qos(prefetch_count=1)
            logger.info("RabbitMQ connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def callback(self, ch, method, properties, body):
        """
        Process incoming messages from RabbitMQ.
        This is called automatically by pika for each message received.
        """
        logger.info(f"Received message with correlation_id: {properties.correlation_id}")
        
        try:
            # Parse the incoming message
            data = json.loads(body)
            logger.info(f"Message content: {data}")
            # Process the arqueo operation
            result = operacion_arqueo(data['operation_data']['operation'])
            
            logger.info(f"RESULTADO OPERACIÓN ARQUEO.......: {result}")
            # Prepare response
            response = {
                'status': result.status.value,
                'operation_id': data.get('task_id'),
                'result': dataclasses.asdict(result)
            }
            
            # Send response back through RabbitMQ
            ch.basic_publish(
                exchange='',
                routing_key=properties.reply_to,
                properties=pika.BasicProperties(
                    correlation_id=properties.correlation_id
                ),
                
                body=json.dumps(response, cls=OperationEncoder)
            )
            
            # Acknowledge the message was processed successfully
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Successfully processed message {properties.correlation_id}")
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            # Negative acknowledgment - message will be requeued
            ch.basic_nack(delivery_tag=method.delivery_tag)

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
        except Exception as e:
            logger.error(f"Error while shutting down: {e}")