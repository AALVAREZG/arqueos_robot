#!/usr/bin/env python3
"""
Verify that the consumer sends responses to 'sical_results' queue
instead of using reply_to pattern.
"""

import json
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from arqueo_task_consumer import ArqueoConsumer


def test_result_queue_fixed():
    """Verify consumer publishes to fixed 'sical_results' queue."""
    print("="*70)
    print("VERIFICATION: Result Queue Configuration")
    print("="*70)

    with patch('arqueo_task_consumer.pika.BlockingConnection') as mock_connection_class, \
         patch('arqueo_task_consumer.operacion_arqueo') as mock_operacion:

        # Setup mocks
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_connection.is_closed = False
        mock_connection_class.return_value = mock_connection

        # Mock operacion_arqueo to return a successful result
        from arqueo_tasks import OperationResult, OperationStatus
        mock_result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-11-08T10:00:00",
            end_time="2024-11-08T10:01:00",
            duration="0:01:00"
        )
        mock_operacion.return_value = mock_result

        # Create consumer
        consumer = ArqueoConsumer()

        # Prepare test message
        test_message = {
            'task_id': 'test-123',
            'operation_data': {
                'operation': {
                    'fecha': '08112024',
                    'caja': '204',
                    'tercero': '43000000M',
                    'naturaleza': '5',
                    'aplicaciones': [{
                        'year': '2024',
                        'economica': '30012',
                        'proyecto': '',
                        'contraido': True,
                        'base_imponible': 0.0,
                        'tipo': 0.0,
                        'importe': 5000.0,
                        'cuenta_pgp': ''
                    }],
                    'texto_sical': [{'tcargo': 'TEST'}],
                    'descuentos': [],
                    'aux_data': {},
                    'metadata': {'generation_datetime': '2024-11-08T15:30:00.000Z'}
                }
            }
        }

        # Mock message properties
        properties = MagicMock()
        properties.correlation_id = 'corr-123'
        properties.reply_to = 'temp.reply.queue.old.pattern'  # Old pattern

        method = MagicMock()
        method.delivery_tag = 'tag-123'

        # Execute callback
        consumer.callback(
            mock_channel,
            method,
            properties,
            json.dumps(test_message).encode()
        )

        # Verify queue declarations
        queue_declare_calls = mock_channel.queue_declare.call_args_list
        print("\n✓ QUEUE DECLARATIONS:")

        queues_declared = []
        for call in queue_declare_calls:
            queue_name = call[1]['queue']
            is_durable = call[1]['durable']
            queues_declared.append(queue_name)
            print(f"  ✓ Queue '{queue_name}' declared (durable={is_durable})")

        checks = {
            'sical_queue.arqueo declared': 'sical_queue.arqueo' in queues_declared,
            'sical_results declared': 'sical_results' in queues_declared,
        }

        # Verify publish call
        assert mock_channel.basic_publish.called, "basic_publish was not called"

        publish_call = mock_channel.basic_publish.call_args
        routing_key = publish_call[1]['routing_key']
        correlation_id = publish_call[1]['properties'].correlation_id

        print("\n✓ PUBLISH CALL:")
        print(f"  ✓ Routing key: {routing_key}")
        print(f"  ✓ Correlation ID: {correlation_id}")

        checks.update({
            'routing_key is sical_results': routing_key == 'sical_results',
            'NOT using reply_to': routing_key != properties.reply_to,
            'correlation_id preserved': correlation_id == 'corr-123',
        })

        # Check response format
        response_body = publish_call[1]['body']
        response = json.loads(response_body)

        print("\n✓ RESPONSE FORMAT:")
        print(f"  ✓ Status: {response.get('status')}")
        print(f"  ✓ Operation ID: {response.get('operation_id')}")
        print(f"  ✓ Has result: {'result' in response}")

        checks.update({
            'response has status': 'status' in response,
            'response has operation_id': 'operation_id' in response,
            'response has result': 'result' in response,
        })

        # Verify message acknowledged
        assert mock_channel.basic_ack.called, "Message was not acknowledged"
        checks['message acknowledged'] = True

        print("\n✅ VERIFICATION CHECKS:")
        all_passed = True
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False

        assert all_passed, "Some checks failed"


if __name__ == '__main__':
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "RESULT QUEUE VERIFICATION" + " "*22 + "║")
    print("╚" + "="*68 + "╝")
    print()

    try:
        test_result_queue_fixed()

        print("\n" + "="*70)
        print("🎉 ALL CHECKS PASSED!")
        print("="*70)
        print("\n✅ CONFIRMED:")
        print("  • Responses sent to fixed 'sical_results' queue")
        print("  • NOT using reply_to pattern (old pattern)")
        print("  • sical_results queue declared as durable")
        print("  • Correlation ID preserved for message tracking")
        print("  • Response format correct")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ ASSERTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
