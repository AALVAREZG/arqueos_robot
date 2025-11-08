#!/usr/bin/env python3
"""Simple test script to verify arqueo migration to new JSON structure."""

import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import only the data transformation functions (not the robocorp ones)
from arqueo_tasks import create_arqueo_data, create_aplicaciones


def test_new_structure():
    """Test processing of new JSON structure."""
    print("Testing NEW JSON structure...")

    # Sample data with NEW structure
    operation_data = {
        'fecha': '08112024',
        'caja': '204',
        'expediente': '',
        'tercero': '43000000M',
        'texto_sical': [{'tcargo': 'RECAUDADO TRIBUTOS VARIOS C60'}],
        'naturaleza': '5',
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '30012',
                'proyecto': '',
                'contraido': True,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 5000.0,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-11-08T15:30:00.000Z'
        }
    }

    # Transform the data
    result = create_arqueo_data(operation_data)

    # Verify basic fields
    assert result['fecha'] == '08112024', f"Expected fecha '08112024', got {result['fecha']}"
    assert result['caja'] == '204', f"Expected caja '204', got {result['caja']}"
    assert result['tercero'] == '43000000M', f"Expected tercero '43000000M', got {result['tercero']}"
    assert result['naturaleza'] == '5', f"Expected naturaleza '5', got {result['naturaleza']}"
    assert result['resumen'] == 'RECAUDADO TRIBUTOS VARIOS C60', f"Expected resumen, got {result['resumen']}"

    # Verify new fields
    assert 'descuentos' in result, "Missing 'descuentos' field"
    assert 'aux_data' in result, "Missing 'aux_data' field"
    assert 'metadata' in result, "Missing 'metadata' field"

    # Verify aplicaciones
    assert len(result['aplicaciones']) == 1, f"Expected 1 aplicacion, got {len(result['aplicaciones'])}"

    app = result['aplicaciones'][0]
    assert app['partida'] == '30012', f"Expected partida '30012', got {app['partida']}"
    assert app['importe'] == '5000,0', f"Expected importe '5000,0', got {app['importe']}"
    assert app['contraido'] == True, f"Expected contraido True, got {app['contraido']}"
    assert app['year'] == '2024', f"Expected year '2024', got {app['year']}"
    assert 'base_imponible' in app, "Missing 'base_imponible' field"
    assert 'tipo' in app, "Missing 'tipo' field"
    assert 'cuenta_pgp' in app, "Missing 'cuenta_pgp' field"

    print("✅ Basic test PASSED")


def test_multiple_aplicaciones():
    """Test with multiple aplicaciones."""
    print("\nTesting multiple aplicaciones...")

    operation_data = {
        'fecha': '08112024',
        'caja': '207',
        'expediente': '',
        'tercero': '000',
        'texto_sical': [{'tcargo': 'TRANSF. N/F: LICENCIA DE OBRA'}],
        'naturaleza': '4',
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '290',
                'proyecto': '',
                'contraido': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 1200.0,
                'cuenta_pgp': ''
            },
            {
                'year': '2024',
                'economica': '20104',
                'proyecto': '',
                'contraido': True,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 200.0,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-11-08T15:30:00.000Z'
        }
    }

    result = create_arqueo_data(operation_data)

    assert len(result['aplicaciones']) == 2, f"Expected 2 aplicaciones, got {len(result['aplicaciones'])}"

    # Check first aplicacion
    app1 = result['aplicaciones'][0]
    assert app1['partida'] == '290', f"Expected partida '290', got {app1['partida']}"
    assert app1['contraido'] == False, f"Expected contraido False, got {app1['contraido']}"
    assert app1['cuenta'] == '733', f"Expected cuenta '733', got {app1['cuenta']}"

    # Check second aplicacion
    app2 = result['aplicaciones'][1]
    assert app2['partida'] == '20104', f"Expected partida '20104', got {app2['partida']}"
    assert app2['contraido'] == True, f"Expected contraido True, got {app2['contraido']}"
    assert app2['cuenta'] == '561', f"Expected cuenta '561', got {app2['cuenta']}"

    print("✅ Multiple aplicaciones test PASSED")


def test_contraido_numeric():
    """Test contraido with numeric value."""
    print("\nTesting numeric contraido...")

    operation_data = {
        'fecha': '08112024',
        'caja': '203',
        'expediente': '',
        'tercero': '25352229L',
        'texto_sical': [{'tcargo': 'FRACCIONAMIENTO DEUDA'}],
        'naturaleza': '5',
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '39900',
                'proyecto': '',
                'contraido': 2500046,  # Numeric contraido
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 50.0,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-11-08T15:30:00.000Z'
        }
    }

    result = create_arqueo_data(operation_data)

    app = result['aplicaciones'][0]
    assert app['contraido'] == 2500046, f"Expected contraido 2500046, got {app['contraido']}"
    assert isinstance(app['contraido'], int), f"Expected int, got {type(app['contraido'])}"

    print("✅ Numeric contraido test PASSED")


def test_with_proyecto():
    """Test aplicacion with proyecto."""
    print("\nTesting aplicacion with proyecto...")

    operation_data = {
        'fecha': '08112024',
        'caja': '207',
        'expediente': '',
        'tercero': '45575500B',
        'texto_sical': [{'tcargo': 'TRANSF N/F SUBVENCION GUARDERIA'}],
        'naturaleza': '4',
        'aplicaciones': [
            {
                'year': '2024',
                'economica': '45002',
                'proyecto': '24000014',
                'contraido': False,
                'base_imponible': 0.0,
                'tipo': 0.0,
                'importe': 1500.0,
                'cuenta_pgp': ''
            }
        ],
        'descuentos': [],
        'aux_data': {},
        'metadata': {
            'generation_datetime': '2024-11-08T15:30:00.000Z'
        }
    }

    result = create_arqueo_data(operation_data)

    app = result['aplicaciones'][0]
    assert app['proyecto'] == '24000014', f"Expected proyecto '24000014', got {app['proyecto']}"

    print("✅ Proyecto test PASSED")


if __name__ == '__main__':
    try:
        test_new_structure()
        test_multiple_aplicaciones()
        test_contraido_numeric()
        test_with_proyecto()

        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print("\nMigration Summary:")
        print("  ✓ New 'aplicaciones' structure supported")
        print("  ✓ Field mapping: economica → partida (internal)")
        print("  ✓ Field mapping: importe → importe (formatted)")
        print("  ✓ Contraido: boolean and integer values supported")
        print("  ✓ New fields extracted: year, proyecto, base_imponible, tipo, cuenta_pgp")
        print("  ✓ New top-level fields: descuentos, aux_data, metadata")
        print("  ✓ No Total row filtering needed")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
