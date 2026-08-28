# services/rabbitmq/consumer.py

import pika
import json
import dataclasses
import socket
import comtypes
from typing import Optional, Callable
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS
from arqueo_tasks import OperationEncoder, operacion_arqueo, set_heartbeat_callback
import document_mode as document_mode_mod
from rabbit_heartbeat import HeartbeatPublisher
from logging_setup import (
    configure_logging, get_logger, bind_task, unbind_task,
    phase as log_phase, ok as log_ok, warn as log_warn,
    fail as log_fail, detail as log_detail,
)

configure_logging()  # idempotent
logger = get_logger(__name__)


def _capture_info(envelope: Optional[dict]) -> Optional[dict]:
    """
    Compact contable-capture summary for the GUI/history (spec v2).
    None when the task didn't run the capture path (flag OFF / not
    finalized). The base64 `data` is deliberately excluded.
    """
    if not envelope:
        return None
    return {
        'filename': envelope.get('filename'),
        'size_bytes': envelope.get('size_bytes'),
        'page_count': envelope.get('page_count'),
        'sha256': envelope.get('sha256'),
        'status': envelope.get('capture_status'),  # CAPTURED | FAILED
        'error': envelope.get('capture_error'),
    }


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
        # Latido a RabbitMQ (spec §6.3). `arqueo_tasks` ya generaba estos pasos
        # via TASK_CALLBACK, pero el consumidor nunca lo registraba: iban solo
        # a la GUI y se perdian. Registrarlo es todo el cambio.
        self.heartbeat: Optional[HeartbeatPublisher] = None
        self.hostname = socket.gethostname()
        self.setup_connection()
        set_heartbeat_callback(self._publish_heartbeat)

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

            self.heartbeat = HeartbeatPublisher(self.channel, 'arqueo', logger)
            self.heartbeat.declare()

            log_ok(logger, 'CONN', 'RabbitMQ connected')

            if STATUS_CALLBACK:
                STATUS_CALLBACK('connected')

        except Exception as e:
            log_fail(logger, 'CONN', f'RabbitMQ connect failed: {e}')
            if STATUS_CALLBACK:
                STATUS_CALLBACK('disconnected')
            raise

    def _publish_heartbeat(self, step, **_kwargs):
        """
        Publica cada paso del robot a RabbitMQ.

        Ranura propia, separada de TASK_CALLBACK: la GUI registra la suya y con
        una sola el ultimo en llegar borraba al otro.

        Cada paso rearma la ventana de silencio del productor (§6.4): pasa de
        preguntar «¿han pasado 75 s desde que publique?» -que mata tareas
        vivas- a «¿han pasado 75 s sin noticias de esta tarea?». Nunca lanza.
        """
        try:
            if self.heartbeat and step:
                self.heartbeat.beat(step)
        except Exception as exc:  # noqa: BLE001
            log_detail(logger, 'HEARTBEAT', f'publish failed: {exc}')

    def callback(self, ch, method, properties, body):
        """
        Process incoming messages from RabbitMQ.
        This is called automatically by pika for each message received.
        """
        task_id = None
        try:
            # Parse the incoming message
            data = json.loads(body)
            task_id = data.get('task_id', 'unknown')
            bind_task(task_id)
            log_phase(logger, 'RECEIVED',
                      f"arqueo task {task_id} (corr={properties.correlation_id})")
            log_detail(logger, 'RECEIVED', f"payload={data}")

            # Modo de documento: lo decide el productor y viaja en el
            # mensaje (spec §4). El consumidor deja de tener interruptor;
            # CONTABLE_CAPTURE_ENABLED queda como reserva para mensajes que no
            # traigan el campo, lo que permite desplegar el productor primero.
            doc_mode = document_mode_mod.document_mode_from_message(data)
            log_detail(logger, 'PARSED',
                       f'document_mode={doc_mode or "(reserva CONTABLE_CAPTURE_ENABLED)"}')

            if self.heartbeat:
                self.heartbeat.bind(properties.correlation_id, task_id=task_id)
                self.heartbeat.beat('Task received')

            # Notify GUI: task received
            if STATUS_CALLBACK:
                STATUS_CALLBACK('task_received', task_id=task_id)

            # Extract operation details (the real data is inside 'detalle')
            operation = data.get('operation_data', {}).get('operation', {})
            detalle = operation.get('detalle', {})

            # Duplicate-policy fields are sent at the message root by
            # sical-robot's createTaskMessage, but operacion_arqueo only sees
            # the `operation` dict. Merge them down so the two-phase duplicate
            # flow (check_only -> force_create + token) reaches the processor.
            for policy_field in ('duplicate_policy', 'duplicate_confirmation_token',
                                 'duplicate_check_id'):
                if policy_field in data and policy_field not in operation:
                    operation[policy_field] = data[policy_field]
                    log_detail(logger, 'PARSED',
                               f'merged {policy_field} from message root')
            log_detail(logger, 'PARSED',
                       f"operation keys={list(operation.keys())} "
                       f"detalle keys={list(detalle.keys())}")

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

            log_phase(logger, 'PARSED',
                      f"op#{operation_number or '-'} importe={total_amount} "
                      f"fecha={fecha} caja={caja} tercero={tercero} "
                      f"nat={naturaleza} lineas={total_line_items}")

            # Spec v2: the consumer no longer receives attachments. It runs
            # the SICAL op and (behind the rollout flag) captures the
            # contable PDF, returned to sical-robot in the result message.

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

            # Process the arqueo operation.
            result = operacion_arqueo(
                data['operation_data']['operation'],
                task_id,
                doc_mode=doc_mode,
            )

            log_detail(logger, 'RESULT', f"OperationResult={result}")
            # Prepare response
            # `hostname` es como el productor descubre el mapa de asientos
            # (spec §3): un asiento ES una maquina, y el asiento se descubre,
            # no se configura -mover este consumidor a una VM nueva no exige
            # tocar ningun JSON-.
            response = {
                'status': result.status.value,
                'operation_id': task_id,
                'result': dataclasses.asdict(result),
                'hostname': self.hostname,
                'document_mode': doc_mode,
            }

            # Spec v2 §2.2: return the captured contable PDF envelope
            # (base64 + metadata) so sical-robot can merge/print/stage.
            # Only present when the capture path ran (flag ON + finalized).
            contable = getattr(result, '_contable_document', None)
            if contable:
                response['contable_document'] = contable
                cs = contable.get('capture_status')
                if cs == 'CAPTURED':
                    log_phase(logger, 'RESULT',
                              f"returning contable {contable.get('page_count')}p / "
                              f"{contable.get('size_bytes')} B to producer")
                else:
                    log_fail(logger, 'RESULT',
                             f"contable not returned: "
                             f"{contable.get('capture_error') or cs}")
            else:
                log_detail(logger, 'RESULT',
                           'no contable (capture flag OFF or not finalized)')

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

            # Notify GUI: check result status to determine if completed or failed
            from arqueo_tasks import OperationStatus
            succeeded = result.status in (OperationStatus.COMPLETED,
                                          OperationStatus.INCOMPLETED)
            if succeeded:
                log_ok(logger, 'DONE',
                       f"{result.status.value} (op#{result.num_operacion or '-'}, "
                       f"{result.duration or '?'})")
            else:
                log_fail(logger, 'FAILED',
                         f"{result.status.value}: {result.error or 'unknown'}")
            if STATUS_CALLBACK:
                capture_info = _capture_info(getattr(result, '_contable_document', None))
                STATUS_CALLBACK('task_completed' if succeeded else 'task_failed',
                                task_id=task_id, capture_info=capture_info)

        except Exception as e:
            log_fail(logger, 'CONSUMER', f"error processing message: {e}", exc=True)
            # Negative acknowledgment - message will be requeued
            ch.basic_nack(delivery_tag=method.delivery_tag)

            # Notify GUI: task failed
            if STATUS_CALLBACK and task_id:
                STATUS_CALLBACK('task_failed', task_id=task_id)
        finally:
            if self.heartbeat:
                self.heartbeat.unbind()
            unbind_task()

    def start_consuming(self):
        """Start consuming messages from the queue"""
        # Initialize COM for Windows UI Automation at thread level
        # This ensures COM stays initialized across all task executions
        # and avoids COM state issues between successive tasks
        try:
            comtypes.CoInitialize()
            log_detail(logger, 'CONN', 'COM initialized for consumer thread')
        except Exception as e:
            log_detail(logger, 'CONN', f'COM init warning (may already be init): {e}')

        try:
            log_phase(logger, 'CONN', f'consuming from {self.queue_name} - waiting for tasks')

            # Register the callback function to be called when messages arrive
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.callback
            )

            # Start consuming messages - this blocks until stop_consuming() is called
            self.channel.start_consuming()

        except KeyboardInterrupt:
            log_phase(logger, 'CONN', 'interrupt received - shutting down')
            self.stop_consuming()
        except Exception as e:
            log_fail(logger, 'CONN', f'consume error: {e}', exc=True)
            self.stop_consuming()
            raise
        finally:
            # Uninitialize COM when consumer thread exits
            try:
                comtypes.CoUninitialize()
                log_detail(logger, 'CONN', 'COM uninitialized for consumer thread')
            except Exception as e:
                log_detail(logger, 'CONN', f'COM uninit error: {e}')

    def stop_consuming(self):
        """Stop consuming messages and close connections"""
        try:
            if self.channel:
                self.channel.stop_consuming()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            log_phase(logger, 'CONN', 'consumer shut down')

            if STATUS_CALLBACK:
                STATUS_CALLBACK('disconnected')

        except Exception as e:
            log_fail(logger, 'CONN', f'shutdown error: {e}')

    def start(self):
        """Convenience method to start the consumer (alias for start_consuming)"""
        self.start_consuming()

    def stop(self):
        """Convenience method to stop the consumer (alias for stop_consuming)"""
        self.stop_consuming()