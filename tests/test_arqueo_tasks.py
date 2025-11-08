"""
Unit tests for arqueo_tasks.py module.

Tests cover:
- Data transformation functions
- OperationResult and OperationStatus
- Business logic functions
"""

import pytest
from datetime import datetime
from arqueo_tasks import (
    create_arqueo_data,
    create_aplicaciones,
    clean_value,
    OperationResult,
    OperationStatus,
    OperationEncoder,
    partidas_cuentaPG
)
import json


class TestCleanValue:
    """Tests for the clean_value function."""

    @pytest.mark.unit
    def test_boolean_true_unchanged(self):
        """Test that boolean True remains True."""
        assert clean_value(True) is True

    @pytest.mark.unit
    def test_boolean_false_unchanged(self):
        """Test that boolean False remains False."""
        assert clean_value(False) is False

    @pytest.mark.unit
    def test_string_true_converts_to_boolean(self):
        """Test that string 'true' converts to boolean True."""
        assert clean_value('true') is True
        assert clean_value('True') is True
        assert clean_value('TRUE') is True

    @pytest.mark.unit
    def test_string_false_converts_to_boolean(self):
        """Test that string 'false' converts to boolean False."""
        assert clean_value('false') is False
        assert clean_value('False') is False
        assert clean_value('FALSE') is False

    @pytest.mark.unit
    def test_regular_string_converts_to_lowercase(self):
        """Test that regular strings are converted to lowercase."""
        assert clean_value('Test String') == 'test string'
        assert clean_value('UPPERCASE') == 'uppercase'
        assert clean_value('MiXeD') == 'mixed'

    @pytest.mark.unit
    def test_integer_converts_to_string(self):
        """Test that integers are converted to strings."""
        assert clean_value(123) == '123'
        assert clean_value(0) == '0'
        assert clean_value(-456) == '-456'

    @pytest.mark.unit
    def test_empty_string(self):
        """Test behavior with empty string."""
        result = clean_value('')
        assert result == ''

    @pytest.mark.unit
    def test_parametrized_values(self, clean_value_test_cases):
        """Test multiple values using parametrized fixture."""
        for input_val, expected, description in clean_value_test_cases:
            result = clean_value(input_val)
            assert result == expected, f"Failed: {description}"


class TestCreateAplicaciones:
    """Tests for the create_aplicaciones function."""

    @pytest.mark.unit
    def test_basic_aplicaciones_transformation(self, sample_aplicaciones):
        """Test basic transformation of aplicaciones data."""
        result = create_aplicaciones(sample_aplicaciones)

        # Should exclude the last item (total)
        assert len(result) == 3

        # Check first aplicacion
        assert result[0]['partida'] == '130'
        assert result[0]['importe'] == '100,50'
        assert result[0]['contraido'] is False
        assert result[0]['cuenta'] == '727'  # From partidas_cuentaPG mapping
        assert result[0]['otro'] is False

    @pytest.mark.unit
    def test_aplicacion_with_proyecto(self, sample_aplicaciones):
        """Test that proyecto field is preserved."""
        result = create_aplicaciones(sample_aplicaciones)

        # Second item has proyecto
        assert result[1]['proyecto'] == 'PROJ001'

    @pytest.mark.unit
    def test_unmapped_partida_returns_default(self, sample_aplicaciones):
        """Test that unmapped partida codes return '000'."""
        result = create_aplicaciones(sample_aplicaciones)

        # Third item has partida '999' which is not in mapping
        assert result[2]['cuenta'] == '000'

    @pytest.mark.unit
    def test_contraido_field_handling(self, sample_aplicaciones):
        """Test that contraido field is properly cleaned."""
        result = create_aplicaciones(sample_aplicaciones)

        assert result[0]['contraido'] is False
        assert result[1]['contraido'] is True

    @pytest.mark.unit
    def test_empty_aplicaciones_list(self):
        """Test with only total item (edge case)."""
        final_data = [{'total': '0,00'}]
        result = create_aplicaciones(final_data)

        assert len(result) == 0

    @pytest.mark.unit
    def test_partida_type_conversion(self):
        """Test that partida is converted to string."""
        final_data = [
            {'partida': 130, 'IMPORTE_PARTIDA': '100,00'},  # Integer partida
            {'total': '100,00'}
        ]
        result = create_aplicaciones(final_data)

        assert result[0]['partida'] == '130'
        assert isinstance(result[0]['partida'], str)

    @pytest.mark.unit
    def test_known_partida_mappings(self):
        """Test several known partida to cuenta mappings."""
        test_cases = [
            ('130', '727'),    # IAE
            ('300', '740'),    # SERVICIO ABAST AGUA
            ('290', '733'),    # ICIO OBRAS
            ('42000', '7501'), # PIE. PARTICIP TRIB ESTADO
        ]

        for partida, expected_cuenta in test_cases:
            final_data = [
                {'partida': partida, 'IMPORTE_PARTIDA': '100,00'},
                {'total': '100,00'}
            ]
            result = create_aplicaciones(final_data)
            assert result[0]['cuenta'] == expected_cuenta, \
                f"Partida {partida} should map to {expected_cuenta}"


class TestCreateArqueoData:
    """Tests for the create_arqueo_data function."""

    @pytest.mark.unit
    def test_basic_data_transformation(self, sample_operation_data, expected_arqueo_data):
        """Test basic transformation from operation_data to arqueo_data."""
        result = create_arqueo_data(sample_operation_data)

        assert result['fecha'] == expected_arqueo_data['fecha']
        assert result['caja'] == expected_arqueo_data['caja']
        assert result['expediente'] == 'rbt-apunte-arqueo'
        assert result['tercero'] == expected_arqueo_data['tercero']
        assert result['naturaleza'] == expected_arqueo_data['naturaleza']
        assert result['resumen'] == expected_arqueo_data['resumen']

    @pytest.mark.unit
    def test_default_naturaleza_value(self):
        """Test that naturaleza defaults to '4' when not provided."""
        operation_data = {
            'fecha': '01/12/2024',
            'caja': '001',
            'tercero': '12345678A',
            'texto_sical': [{'tcargo': 'Test'}],
            'final': [{'total': '0,00'}]
        }
        result = create_arqueo_data(operation_data)

        assert result['naturaleza'] == '4'

    @pytest.mark.unit
    def test_naturaleza_5_preserved(self, sample_operation_data_naturaleza_5):
        """Test that naturaleza=5 is preserved."""
        result = create_arqueo_data(sample_operation_data_naturaleza_5)

        assert result['naturaleza'] == '5'

    @pytest.mark.unit
    def test_expediente_always_set(self, sample_operation_data):
        """Test that expediente is always set to 'rbt-apunte-arqueo'."""
        result = create_arqueo_data(sample_operation_data)

        assert result['expediente'] == 'rbt-apunte-arqueo'

    @pytest.mark.unit
    def test_resumen_extraction(self, sample_operation_data):
        """Test that resumen is correctly extracted from texto_sical."""
        result = create_arqueo_data(sample_operation_data)

        assert result['resumen'] == 'Test arqueo operation'

    @pytest.mark.unit
    def test_aplicaciones_processing(self, sample_operation_data):
        """Test that aplicaciones are properly processed."""
        result = create_arqueo_data(sample_operation_data)

        assert 'aplicaciones' in result
        assert isinstance(result['aplicaciones'], list)
        assert len(result['aplicaciones']) == 3  # Excludes total

    @pytest.mark.unit
    def test_empty_texto_sical_handling(self):
        """Test handling of empty texto_sical."""
        operation_data = {
            'fecha': '01/12/2024',
            'caja': '001',
            'tercero': '12345678A',
            'texto_sical': [{}],  # Empty dict
            'final': [{'total': '0,00'}]
        }
        result = create_arqueo_data(operation_data)

        assert result['resumen'] is None


class TestOperationStatus:
    """Tests for the OperationStatus enum."""

    @pytest.mark.unit
    def test_status_values(self):
        """Test that all expected status values exist."""
        assert OperationStatus.PENDING.value == "PENDING"
        assert OperationStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert OperationStatus.COMPLETED.value == "COMPLETED"
        assert OperationStatus.INCOMPLETED.value == "INCOMPLETED"
        assert OperationStatus.FAILED.value == "FAILED"

    @pytest.mark.unit
    def test_to_json_method(self):
        """Test that to_json() returns the string value."""
        assert OperationStatus.COMPLETED.to_json() == "COMPLETED"
        assert OperationStatus.FAILED.to_json() == "FAILED"

    @pytest.mark.unit
    def test_enum_comparison(self):
        """Test enum value comparison."""
        status = OperationStatus.COMPLETED
        assert status == OperationStatus.COMPLETED
        assert status != OperationStatus.FAILED


class TestOperationResult:
    """Tests for the OperationResult dataclass."""

    @pytest.mark.unit
    def test_basic_instantiation(self):
        """Test creating a basic OperationResult."""
        init_time = datetime.now()
        result = OperationResult(
            status=OperationStatus.PENDING,
            init_time=str(init_time)
        )

        assert result.status == OperationStatus.PENDING
        assert result.init_time == str(init_time)
        assert result.end_time is None
        assert result.duration is None
        assert result.error is None
        assert result.num_operacion is None
        assert result.total_operacion is None
        assert result.suma_aplicaciones is None
        assert result.sical_is_open is False

    @pytest.mark.unit
    def test_full_result_data(self):
        """Test OperationResult with all fields populated."""
        init_time = datetime.now()
        end_time = datetime.now()

        result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time=str(init_time),
            end_time=str(end_time),
            duration="0:00:05.123456",
            error=None,
            num_operacion="12345",
            total_operacion=851.25,
            suma_aplicaciones=851.25,
            sical_is_open=True
        )

        assert result.status == OperationStatus.COMPLETED
        assert result.num_operacion == "12345"
        assert result.total_operacion == 851.25
        assert result.suma_aplicaciones == 851.25
        assert result.sical_is_open is True

    @pytest.mark.unit
    def test_failed_result_with_error(self):
        """Test OperationResult for a failed operation."""
        result = OperationResult(
            status=OperationStatus.FAILED,
            init_time=str(datetime.now()),
            error="SICAL window not found"
        )

        assert result.status == OperationStatus.FAILED
        assert result.error == "SICAL window not found"


class TestOperationEncoder:
    """Tests for the custom JSON encoder."""

    @pytest.mark.unit
    def test_encode_operation_status(self):
        """Test encoding OperationStatus enum."""
        status = OperationStatus.COMPLETED
        encoded = json.dumps(status, cls=OperationEncoder)

        assert encoded == '"COMPLETED"'

    @pytest.mark.unit
    def test_encode_operation_result(self):
        """Test encoding OperationResult dataclass."""
        result = OperationResult(
            status=OperationStatus.COMPLETED,
            init_time="2024-12-01 10:00:00",
            end_time="2024-12-01 10:05:00",
            duration="0:05:00",
            num_operacion="12345",
            total_operacion=100.50,
            suma_aplicaciones=100.50,
            sical_is_open=True
        )

        encoded = json.dumps(result, cls=OperationEncoder)
        decoded = json.loads(encoded)

        assert decoded['status'] == 'COMPLETED'
        assert decoded['num_operacion'] == '12345'
        assert decoded['total_operacion'] == 100.50
        assert decoded['sical_is_open'] is True

    @pytest.mark.unit
    def test_encode_complex_object(self):
        """Test encoding a dict containing OperationResult."""
        result = OperationResult(
            status=OperationStatus.PENDING,
            init_time="2024-12-01 10:00:00"
        )

        data = {
            'task_id': 'test-123',
            'result': result
        }

        encoded = json.dumps(data, cls=OperationEncoder)
        decoded = json.loads(encoded)

        assert decoded['task_id'] == 'test-123'
        assert decoded['result']['status'] == 'PENDING'


class TestPartidasMapping:
    """Tests for the partidas_cuentaPG mapping dictionary."""

    @pytest.mark.unit
    def test_mapping_exists(self):
        """Test that the mapping dictionary is not empty."""
        assert len(partidas_cuentaPG) > 0

    @pytest.mark.unit
    def test_known_mappings(self):
        """Test several known partida mappings."""
        assert partidas_cuentaPG['130'] == '727'
        assert partidas_cuentaPG['300'] == '740'
        assert partidas_cuentaPG['332'] == '742'
        assert partidas_cuentaPG['45000'] == '7501'

    @pytest.mark.unit
    def test_special_mapping_with_list(self):
        """Test that partida 45002 has a list value."""
        assert isinstance(partidas_cuentaPG['45002'], list)
        assert partidas_cuentaPG['45002'] == ['9411', '24000014']

    @pytest.mark.unit
    def test_all_keys_are_strings(self):
        """Test that all mapping keys are strings."""
        for key in partidas_cuentaPG.keys():
            assert isinstance(key, str), f"Key {key} is not a string"

    @pytest.mark.unit
    def test_mapping_retrieval_with_default(self):
        """Test safe retrieval with default value."""
        result = partidas_cuentaPG.get('999999', '000')
        assert result == '000'

        result = partidas_cuentaPG.get('130', '000')
        assert result == '727'
