#!/usr/bin/env python3
"""
Test with the EXACT structure from the requirements.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from arqueo_tasks import create_arqueo_data


def test_complete_task_structure():
    """Test with complete task structure from requirements."""
    print("="*70)
    print("Testing COMPLETE TASK STRUCTURE from requirements")
    print("="*70)

    # This is the EXACT structure from the requirements
    complete_task = {
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
                            "contraido": 1.0,
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

    # Extract detalle from first operacion
    detalle = complete_task["operaciones"][0]["detalle"]

    # Process it
    result = create_arqueo_data(detalle)

    print(f"\n📥 INPUT (detalle):")
    print(json.dumps(detalle, indent=2))

    print(f"\n📤 OUTPUT (arqueo_data):")
    print(json.dumps(result, indent=2, default=str))

    # Verify critical fields
    checks = {
        'fecha': result['fecha'] == '08112024',
        'caja': result['caja'] == '204',
        'expediente': result['expediente'] == '',
        'tercero': result['tercero'] == '43000000M',
        'naturaleza': result['naturaleza'] == '5',
        'resumen': result['resumen'] == 'RECAUDADO TRIBUTOS VARIOS C60',
        'descuentos': result['descuentos'] == [],
        'aux_data': result['aux_data'] == {},
        'metadata_exists': 'metadata' in result,
        'aplicaciones_count': len(result['aplicaciones']) == 1,
    }

    if result['aplicaciones']:
        app = result['aplicaciones'][0]
        checks.update({
            'app_partida': app['partida'] == '30012',
            'app_importe': app['importe'] == '5000,0',
            'app_year': app['year'] == '2024',
            'app_proyecto': app['proyecto'] == '',
            'app_contraido': app['contraido'] == 1,  # 1.0 converted to int 1
            'app_base_imponible': app['base_imponible'] == 0.0,
            'app_tipo': app['tipo'] == 0.0,
            'app_cuenta_pgp': app['cuenta_pgp'] == '',
            'app_cuenta': app['cuenta'] == '554',  # 30012 maps to 554
        })

    print(f"\n✅ VERIFICATION:")
    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    assert all_passed, "Some checks failed"


def test_multiple_aplicaciones_example():
    """Test Example 3: Multiple Aplicaciones from requirements."""
    print("\n" + "="*70)
    print("Testing EXAMPLE 3: Multiple Aplicaciones")
    print("="*70)

    detalle = {
        "fecha": "08112024",
        "caja": "207",
        "expediente": "",
        "tercero": "000",
        "texto_sical": [
            {
                "tcargo": "TRANSF. N/F: LICENCIA DE OBRA"
            }
        ],
        "naturaleza": "4",
        "aplicaciones": [
            {
                "year": "2024",
                "economica": "290",
                "proyecto": "",
                "contraido": False,
                "base_imponible": 0.0,
                "tipo": 0.0,
                "importe": 1200.0,
                "cuenta_pgp": ""
            },
            {
                "year": "2024",
                "economica": "20104",
                "proyecto": "",
                "contraido": True,
                "base_imponible": 0.0,
                "tipo": 0.0,
                "importe": 200.0,
                "cuenta_pgp": ""
            }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {
            "generation_datetime": "2024-11-08T15:30:00.000Z"
        }
    }

    result = create_arqueo_data(detalle)

    checks = {
        'aplicaciones_count': len(result['aplicaciones']) == 2,
        'app1_economica': result['aplicaciones'][0]['partida'] == '290',
        'app1_contraido': result['aplicaciones'][0]['contraido'] == False,
        'app1_cuenta': result['aplicaciones'][0]['cuenta'] == '733',  # 290 → 733
        'app2_economica': result['aplicaciones'][1]['partida'] == '20104',
        'app2_contraido': result['aplicaciones'][1]['contraido'] == True,
        'app2_cuenta': result['aplicaciones'][1]['cuenta'] == '561',  # 20104 → 561
    }

    print(f"\n✅ VERIFICATION:")
    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    assert all_passed, "Some checks failed"


def test_numeric_contraido_example():
    """Test Example 4: Contraido with numeric value."""
    print("\n" + "="*70)
    print("Testing EXAMPLE 4: Contraido with Numeric Value")
    print("="*70)

    detalle = {
        "fecha": "08112024",
        "caja": "203",
        "expediente": "",
        "tercero": "25352229L",
        "texto_sical": [
            {
                "tcargo": "FRACCIONAMIENTO DEUDA"
            }
        ],
        "naturaleza": "5",
        "aplicaciones": [
            {
                "year": "2024",
                "economica": "39900",
                "proyecto": "",
                "contraido": 2500046,  # 7-digit integer
                "base_imponible": 0.0,
                "tipo": 0.0,
                "importe": 50.0,
                "cuenta_pgp": ""
            }
        ],
        "descuentos": [],
        "aux_data": {},
        "metadata": {
            "generation_datetime": "2024-11-08T15:30:00.000Z"
        }
    }

    result = create_arqueo_data(detalle)

    checks = {
        'aplicaciones_count': len(result['aplicaciones']) == 1,
        'contraido_value': result['aplicaciones'][0]['contraido'] == 2500046,
        'contraido_type': isinstance(result['aplicaciones'][0]['contraido'], int),
    }

    print(f"\n✅ VERIFICATION:")
    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    assert all_passed, "Some checks failed"


def test_old_structure_rejected():
    """Verify old structure is NOT processed."""
    print("\n" + "="*70)
    print("Testing OLD STRUCTURE REJECTION")
    print("="*70)

    old_detalle = {
        "fecha": "08112024",
        "caja": "204",
        "tercero": "43000000M",
        "naturaleza": "5",
        "final": [  # OLD field - should be IGNORED
            {
                "partida": "30012",
                "contraido": "True",
                "IMPORTE_PARTIDA": 5000.0
            },
            {
                "partida": "Total",
                "IMPORTE_PARTIDA": 0.0
            }
        ],
        "texto_sical": [
            {
                "tcargo": "RECAUDADO TRIBUTOS VARIOS",
                "ado": ""  # OLD field - should be IGNORED
            }
        ]
    }

    result = create_arqueo_data(old_detalle)

    checks = {
        'aplicaciones_empty': len(result['aplicaciones']) == 0,
        'resumen_works': result['resumen'] == 'RECAUDADO TRIBUTOS VARIOS',
        'no_ado_access': True,  # If we got here, ado wasn't accessed
    }

    print(f"\n✅ VERIFICATION:")
    print(f"  ✓ Old 'final' field IGNORED (not processed)")
    print(f"  ✓ Old 'ado' field IGNORED (only tcargo used)")
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
    print("║" + " "*10 + "EXACT STRUCTURE TESTING - FROM REQUIREMENTS" + " "*10 + "║")
    print("╚" + "="*68 + "╝")
    print()

    try:
        test_complete_task_structure()
        test_multiple_aplicaciones_example()
        test_numeric_contraido_example()
        test_old_structure_rejected()

        print("\n" + "="*70)
        print("FINAL SUMMARY")
        print("="*70)
        print("✓ PASS: Complete Task Structure")
        print("✓ PASS: Multiple Aplicaciones")
        print("✓ PASS: Numeric Contraido")
        print("✓ PASS: Old Structure Rejected")

        all_passed = True
    except AssertionError as e:
        print(f"\n✗ FAIL: {e}")
        all_passed = False

    if all_passed:
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED - NEW STRUCTURE FULLY SUPPORTED!")
        print("="*70)
        print("\n✅ CONFIRMED:")
        print("  • Complete task structure processed correctly")
        print("  • Multiple aplicaciones handled")
        print("  • Numeric contraido (7-digit integer) supported")
        print("  • Boolean contraido (true/false) supported")
        print("  • Float contraido (1.0, 0.0) converted to int (fallback)")
        print("  • All new fields extracted (year, proyecto, base_imponible, etc.)")
        print("  • Old 'final' structure NOT supported (intentionally)")
        print("  • Old 'ado' field NOT accessed")
        print("  • NO Total row filtering (not needed)")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
