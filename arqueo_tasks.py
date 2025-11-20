# Standard library imports
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# Third-party imports
import comtypes
from robocorp import windows
from robocorp.tasks import task

# Optional task callback for GUI integration (progress updates)
TASK_CALLBACK: Optional[Callable] = None


def set_task_callback(callback: Optional[Callable] = None):
    """Set the task callback function for GUI integration."""
    global TASK_CALLBACK
    TASK_CALLBACK = callback


###########
### ARQUEO 1.5
## se pretende hacer uso de rabbitMq para la comunicación entre los procesos
###########

partidas_cuentaPG = {
    '130'   : '727', #IAE
    '300'   : '740', #SERVICIO ABAST AGUA
    '302'   : '740', #SERVICIO DE BASURAS      
    '32900' : '740', #TASAS CEMENTERIO
    '32901' : '740', #PISCINA MUNICIPAL
    '32905' : '740', #TASAS GIMNASIO MUNICIPAL
    '325'   : '740', #TASAS EXPED. DOCUMENTOS
    '332'   : '742', #TOPV EMPRESAS SUMINISTRADORAS
    '389'   : '775', #REINTEGROS
    '399'   : '777', #OTROS INGRESOS DIVERSOS
    '42000' : '7501', #PIE. PARTICIP TRIB ESTADO
    '45000' : '7501', #PATRICA
    '45002' : ['9411', '24000014'], #SUBVENCION GUARDERIA MUNICIPAL
    '290'   : '733', #ICIO OBRAS
    '549'   : '776', #OTRAS RENTAS BIENES INMUEBLES
    '20104' : '561', #FIANZA OBRAS
    '30012' : '554', #INGRESOS CTAS OP PEND APLICACION
    '30016' : '554', #INGRESOS AGENTES RECAUDADORES PEND APLICACION
}

ROBOT_DIR = Path(__file__).parent.absolute()
DATA_FOLDER_NAME = 'data'
DATA_DIR = os.path.join(ROBOT_DIR, DATA_FOLDER_NAME)
PENDING_DIR = os.path.join(DATA_DIR, 'pending')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')
FAILED_DIR = os.path.join(DATA_DIR, 'z_failed')

# SICAL Window Patterns
SICAL_WINDOWS = {
    'main_menu': 'regex:.*FMenuSical',
    'arqueo': 'regex:.*SICAL II 4.2 mtec40',
    'ado220': 'regex:.*SICAL II 4.2 new30',
    'pmp450': 'regex:.*SICAL II 4.2 new30',  # TODO: Update when PMP450 window pattern is known
    'consulta': 'regex:.*SICAL II 4.2 ConOpera',
    'tesoreria': 'regex:.*SICAL II 4.2 TesPagos',
    'filtros': 'regex:.*SICAL II 4.2 FilOpera',
    'confirm_dialog': 'regex:.*Confirm',
    'information_dialog': 'regex:.*Information',
    'error_dialog': 'regex:.*mtec40',
    'visual_documentos': 'regex:.*Visualizador de Documentos de SICAL v2',
    'print_dialog': 'regex:.*Imprimir',
}

# SICAL Menu Paths
SICAL_MENU_PATHS = {
    'ado220': ('GASTOS', 'OPERACIONES DE PRESUPUESTO CORRIENTE'),
    'pmp450': ('GASTOS', 'OPERACIONES DE PRESUPUESTO CORRIENTE'),  # TODO: Verify actual path for PMP450
    'consulta': ('CONSULTAS AVANZADAS', 'CONSULTA DE OPERACIONES'),
    'tesoreria_pagos': ('TESORERIA', 'GESTION DE PAGOS', 'PROCESO DE ORDENACION Y PAGO'),
    'arqueo': ('TESORERIA', 'GESTION DE COBROS', 'ARQUEOS. APLICACION DIRECTA',
               'TRATAMIENTO INDIVIDUALIZADO/RESUMEN'),
}

# =============================================================================
# CONSULTA OPERATION PATHS - UI element locators for consultation window
# =============================================================================

CONSULTA_FORM_PATHS = {
    'id_operacion': 'class:"TEdit" and path:"1|38"',
    'imprimir_button': 'class:"TBitBtn" and name:"Imprimir"',
    'estado_documento': 'class:"TEdit" and path:"1|3"',
    'filtros_button': 'class:"TBitBtn" and name:"Filtros"',
    'salir_button': 'class:"TBitBtn" and name:"Salir"',
}

# =============================================================================
# FILTROS OPERATION PATHS - UI element locators for filters window
# =============================================================================

FILTROS_FORM_PATHS = {
    'arqueos_option': 'class:"TGroupButton" and name:"Arqueos"',
    'tercero': 'class:"TEdit" and path:"2|29"',
    'fecha_desde': 'control:"EditControl" and path:"2|24"',
    'fecha_hasta': 'control:"EditControl" and path:"2|17"',
    'funcional': 'class:"TEdit" and path:"2|34"',
    'economica': 'class:"TEdit" and path:"2|33"',
    'importe_desde': 'class:"TEdit" and path:"2|5"',
    'importe_hasta': 'class:"TEdit" and path:"2|4"',
    'caja': 'class:"Edit" and path:"2|15|1"',
    'consultar_button': 'class:"TBitBtn" and name:"Consultar"',
    'num_registros': 'class:"TEdit" and path:"1|1|2"',
    'texto_operacion': 'class:"TEdit" and path:"2|14"',
    'cerrar_button': 'control:"ButtonControl" and name:"Cerrar"',
}


# =============================================================================
# VISUAL DOCUMENTOS PATHS - UI element locators for document viewer
# =============================================================================

VISUAL_DOCUMENTOS_PATHS = {
    'imprimir_button': 'class:"TBitBtn" and path:"2|2|7"',
    'guardar_pdf_button': 'class:"TBitBtn" and path:"2|2|3"',
    'salir_button': 'class:"TBitBtn" and path:"2|2|6"',
}


# Common Dialog Paths
COMMON_DIALOG_PATHS = {
    'ok_button': 'path:"1|1"',
    'yes_button': 'path:"1|2"',
    'no_button': 'path:"1|3"'
}


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get logger instance
arqueo_logger = logging.getLogger(__name__)

# Finalization flag constant
FINALIZE_SUFFIX = '_FIN'

def check_finalize_flag(texto: str) -> tuple:
    """
    Check if operation text ends with finalize flag and extract clean text.

    Args:
        texto: Operation text that may contain _FIN suffix

    Returns:
        Tuple of (cleaned_text, should_finalize)
    """
    if texto and texto.endswith(FINALIZE_SUFFIX):
        return texto[:-len(FINALIZE_SUFFIX)].strip(), True
    return texto, False

# 1. First, make the Enum JSON-serializable
class OperationStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    INCOMPLETED = "INCOMPLETED"
    FAILED = "FAILED"
    P_DUPLICATED = "P_DUPLICATED"  # Possible duplicate detected

    def to_json(self):
        """Convert enum to string for JSON serialization"""
        return self.value

# 2. Create a custom JSON encoder
class OperationEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, OperationStatus):
            return obj.value
        if isinstance(obj, OperationResult):
            return {
                'status': obj.status.value,
                'init_time': obj.init_time,
                'end_time': obj.end_time,
                'duration': obj.duration,
                'error': obj.error,
                'num_operacion': obj.num_operacion,
                'total_operacion': obj.total_operacion,
                'suma_aplicaciones': obj.suma_aplicaciones,
                'sical_is_open': obj.sical_is_open,
                'similiar_records_encountered': obj.similiar_records_encountered
            }
        return super().default(obj)

@dataclass
class OperationResult:
    status: OperationStatus
    init_time: str
    end_time: Optional[str] = None
    duration: Optional[str] = None
    error: Optional[str] = None
    num_operacion: Optional[str] = None
    total_operacion: Optional[float] = None
    suma_aplicaciones: Optional[float] = None
    sical_is_open: bool = False
    similiar_records_encountered: int = 0

class SicalWindowManager:
    def __init__(self):
        self.ventana_arqueo = None

    def find_arqueo_window(self):
        return windows.find_window('regex:.*SICAL II 4.2 mtec40', raise_error=False)

    def close_window(self):
        if self.ventana_arqueo:
            try:
                boton_cerrar = self.ventana_arqueo.find('name:"Cerrar"', search_depth=8, raise_error=False)
                if boton_cerrar:
                    boton_cerrar.click()
                    self.ventana_arqueo.find('class:"TButton" and name:"No"').click()
            except Exception as e:
                arqueo_logger.exception("Error closing window: %s", str(e))

def _check_for_duplicates(datos_arqueo: Dict[str, Any], result: OperationResult) -> OperationResult:
    """
    Check for duplicate operations using the Consulta window.

    Args:
        datos_arqueo: Operation data to search for
        result: Current operation result

    Returns:
        Updated operation result with duplicate check status
    """
    arqueo_logger.info('Checking for duplicate operations')
    if TASK_CALLBACK:
        TASK_CALLBACK('step', step='Checking for duplicate operations')

    try:
        # Setup consulta window
        if not abrir_ventana_opcion_en_menu(SICAL_MENU_PATHS.get('consulta', None)):
            result.status = OperationStatus.FAILED
            result.error = 'Failed to open Consulta window'
            return result

        time.sleep(1.0)
        ventana_consulta = windows.find_window(SICAL_WINDOWS['consulta'], timeout=8.0, raise_error=False)

        if not ventana_consulta:
            result.status = OperationStatus.FAILED
            result.error = 'Consulta window not found'
            return result

        # Open filters window
        filtros_btton = ventana_consulta.find(CONSULTA_FORM_PATHS['filtros_button'],timeout=2.0, raise_error=False)
        if not filtros_btton:
            result.status = OperationStatus.FAILED
            result.error = 'Filtros button not found'
            return result
        else:
            filtros_btton.click()

        time.sleep(0.5)

        filtros_window = windows.find_window(SICAL_WINDOWS['filtros'], timeout=8.0, raise_error=False)

        if not filtros_window:
            result.status = OperationStatus.FAILED
            result.error = 'Failed to open Filters window'
            return result

        # Fill filter criteria
        wait_time = 0.02
        interval = 0.02
        # Arqueo operation type
        arqueo_option = filtros_window.find(FILTROS_FORM_PATHS['arqueos_option'])
        arqueo_option.click()

        # Tercero
        tercero_field = filtros_window.find(FILTROS_FORM_PATHS['tercero'])
        tercero_field.double_click()
        tercero_field.send_keys(datos_arqueo['tercero'], interval=interval, wait_time=wait_time, send_enter=True)

        # Date range (same date for from and to)
        fecha = datos_arqueo['fecha']
        from_date_field = filtros_window.find(FILTROS_FORM_PATHS['fecha_desde'])
        from_date_field.double_click()
        from_date_field.send_keys(fecha, interval=0.01, wait_time=wait_time, send_enter=True)

        to_date_field = filtros_window.find(FILTROS_FORM_PATHS['fecha_hasta'])
        to_date_field.double_click()
        to_date_field.send_keys(fecha, interval=0.01, wait_time=wait_time, send_enter=True)

        # Caja
        caja_field = filtros_window.find(FILTROS_FORM_PATHS['caja'])
        caja_field.click()
        caja_field.send_keys(datos_arqueo['caja'], interval=0.01, wait_time=wait_time, send_enter=True)

        # Total of aplicaciones
        if TASK_CALLBACK:
            _text = f'processing aplicaciones: {datos_arqueo.get("aplicaciones")}'
            TASK_CALLBACK('step', step=_text)
        
        if datos_arqueo.get('aplicaciones') and len(datos_arqueo['aplicaciones']) > 0:
            total_importe = sum(
                float(app['importe'].replace(',', '.'))
                for app in datos_arqueo.get('aplicaciones')
            )
        else:
            total_importe=0.0
            result.status = OperationStatus.FAILED
            result.error = 'Total aplicaciones calculado == 0'
            return result

        if isinstance(total_importe, (int, float)):
            total_importe_str = str(total_importe).replace('.', ',')
        else:
            total_importe_str = str(total_importe)
        
        # Amount range
        importe_desde = filtros_window.find(FILTROS_FORM_PATHS['importe_desde'])
        importe_desde.double_click()
        importe_desde.send_keys(total_importe_str, interval=0.01, wait_time=wait_time, send_enter=True)

        importe_hasta = filtros_window.find(FILTROS_FORM_PATHS['importe_hasta'])
        importe_hasta.double_click()
        importe_hasta.send_keys(total_importe_str, interval=0.01, wait_time=wait_time, send_enter=True)

        

        # Execute search
        filtros_window.find(FILTROS_FORM_PATHS['consultar_button']).click()
        time.sleep(1.0)

        # Check for results
        modal_error = filtros_window.find(
            'class:"TMessageForm" and name:"Error"',
            timeout=1.5,
            raise_error=False
        )

        if not modal_error:
            # Records found - potential duplicate
            num_registros_element = filtros_window.find(FILTROS_FORM_PATHS['num_registros'], raise_error=False)
            if num_registros_element:
                num_registros = num_registros_element.get_value()
                arqueo_logger.warning(f'Found {num_registros} similar records - possible duplicate')
                result.similiar_records_encountered = int(num_registros) if num_registros else 0
            else:
                result.similiar_records_encountered = 1  # At least one found

            result.status = OperationStatus.P_DUPLICATED
            result.error = f'Possible duplicate operation found, similar records: {result.similiar_records_encountered}'

            # Close filters window
            try:
                filtros_window.find(FILTROS_FORM_PATHS['cerrar_button']).click()
            except:
                pass

            # Close consulta window
            try:
                ventana_consulta.find(CONSULTA_FORM_PATHS['salir_button']).click()
            except:
                pass

            arqueo_logger.warning(f'Duplicate check failed: {result.error}')

        else:
            # No records found - safe to proceed
            result.similiar_records_encountered = 0
            arqueo_logger.info('No similar records found - proceeding with operation')

            # Close error dialog
            filtros_window.find(COMMON_DIALOG_PATHS['ok_button']).click()
            time.sleep(0.2)

            # Close filters window
            filtros_window.find(FILTROS_FORM_PATHS['cerrar_button']).click()
            time.sleep(0.2)

            # Close consulta window
            ventana_consulta.find(CONSULTA_FORM_PATHS['salir_button']).click()
            time.sleep(0.2)

    except windows.ElementNotFound as e:
        arqueo_logger.error(f'Element not found during duplicate check: {e}')
        result.status = OperationStatus.FAILED
        result.error = f'Duplicate check error: {str(e)}'
    except Exception as e:
        arqueo_logger.error(f'Error checking for duplicates: {e}')
        result.status = OperationStatus.FAILED
        result.error = f'Duplicate check error: {str(e)}'

    return result

@task
def operacion_arqueo(operation_data: Dict[str, Any]) -> OperationResult:
    """
    Process an arqueo operation in SICAL system based on received message data.

    Args:
        operation_data: Dictionary containing the operation details from RabbitMQ message

    Returns:
        OperationResult: Object containing the operation results and status
    """
    # NOTE: COM initialization is now handled at the consumer thread level
    # to avoid COM state issues between successive task executions

    arqueo_logger.info('Entry Operación arqueo: %s', operation_data)
    init_time = datetime.now()
    result = OperationResult(
        status=OperationStatus.PENDING,
        init_time=str(init_time),
        sical_is_open=False
    )

    window_manager = SicalWindowManager()

    try:
        # Prepare operation data
        if TASK_CALLBACK:
            TASK_CALLBACK('step', step='Preparing operation data')

        # Extract tipo and detalle from operation_data
        # operation_data structure: {"tipo": "arqueo", "detalle": {...}}
        operation_type = operation_data.get('tipo', 'arqueo')
        detalle = operation_data.get('detalle', {})

        arqueo_logger.info(f'Operation type: {operation_type}')

        datos_arqueo = create_arqueo_data(detalle)
        arqueo_logger.debug('Created arqueo data: %s', datos_arqueo)

        # Check for duplicates BEFORE opening arqueo window (if finalization flag is set)
        finalizar_operacion = datos_arqueo.get('finalizar_operacion', False)
        if finalizar_operacion:
            arqueo_logger.info('Operation marked for finalization - checking for duplicates before opening window')
            result = _check_for_duplicates(datos_arqueo, result)

            # If duplicates found or check failed, abort before opening window
            if result.status == OperationStatus.P_DUPLICATED:
                arqueo_logger.warning('Duplicate detected - aborting operation without opening arqueo window')
                return result

            if result.status == OperationStatus.FAILED:
                arqueo_logger.error('Duplicate check failed - aborting operation without opening arqueo window')
                return result

            # Reset status to continue with operation
            result.status = OperationStatus.PENDING

        # Setup SICAL window
        if TASK_CALLBACK:
            TASK_CALLBACK('step', step='Opening SICAL window')

        if not setup_sical_window(window_manager):
            result.status = OperationStatus.FAILED
            result.error = "Failed to open SICAL window"
            return result
        else:
            result.sical_is_open = True
            result.status = OperationStatus.IN_PROGRESS

        # Process operation (includes validation and printing if _FIN flag is set)
        # Note: Duplicate check is now performed above, before opening the window
        if TASK_CALLBACK:
            TASK_CALLBACK('step', step='Processing arqueo operation')

        result = process_arqueo_operation(window_manager.ventana_arqueo, datos_arqueo, result)



    except Exception as e:
        arqueo_logger.exception("Error in arqueo operation")
        result.status = OperationStatus.FAILED
        result.error = str(e)
        
        if result.sical_is_open:
            handle_error_cleanup(window_manager.ventana_arqueo)
    
    finally:
        # Cleanup
        # arqueo_logger.info("Finalize manually until develop is complete")
        #window_manager.close_window()

        # Calculate duration
        end_time = datetime.now()
        result.end_time = str(end_time)
        result.duration = str(end_time - init_time)

        # NOTE: COM uninitialization is now handled at the consumer thread level

    return result

def create_arqueo_data(operation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform operation data from message into SICAL-compatible format"""
    # Extract aplicaciones from new structure
    aplicaciones_data = operation_data.get('aplicaciones', [])

    # Extract texto and check for finalization flag
    texto_sical = operation_data.get('texto_sical', [{}])
    texto_operacion = texto_sical[0].get('tcargo', '') if texto_sical else ''

    # Check if operation should be finalized (ends with _FIN)
    texto_operacion, finalizar_operacion = check_finalize_flag(texto_operacion)
    arqueo_logger.debug("finalizar operacion?...")
    arqueo_logger.debug(finalizar_operacion)
    
    return {
        'fecha': operation_data.get('fecha'),
        'caja': operation_data.get('caja'),
        'expediente': operation_data.get('expediente', 'rbt-apunte-arqueo'),
        'tercero': operation_data.get('tercero'),
        'naturaleza': operation_data.get('naturaleza', '4'),
        'resumen': texto_operacion,
        'finalizar_operacion': finalizar_operacion,
        'aplicaciones': create_aplicaciones(aplicaciones_data),
        'descuentos': operation_data.get('descuentos', []),
        'aux_data': operation_data.get('aux_data', {}),
        'metadata': operation_data.get('metadata', {})
    }

def clean_value(value):
    arqueo_logger.debug("Processing value: %s (type: %s)", value, type(value).__name__)
    if isinstance(value, bool):
        return value  # Return boolean values as-is
    elif isinstance(value, str) and value.lower() == 'false':
        return False
    elif isinstance(value, str) and value.lower() == 'true':
        return True
    elif isinstance(value, str):
        return value.lower()
    elif isinstance(value, int):
        return str(value)
    # Return the original value if it's not a string or int
    return bool(value)

def create_aplicaciones(aplicaciones_data: list) -> list:
    """Transform aplicaciones data into SICAL-compatible format"""
    aplicaciones = []

    # Process all aplicaciones (no Total row in new structure)
    for aplicacion in aplicaciones_data:
        # Extract economica (was 'partida' in old structure)
        economica = str(aplicacion.get('economica', ''))

        # Extract importe (was 'IMPORTE_PARTIDA' in old structure)
        importe = aplicacion.get('importe', 0.0)
        # Convert to string with comma decimal separator for SICAL
        if isinstance(importe, (int, float)):
            importe = str(importe).replace('.', ',')
        else:
            importe = str(importe)

        # Extract contraido (NEW structure: boolean or 7-digit integer)
        contraido = aplicacion.get('contraido', False)
        # Keep as-is: boolean or integer (no float support)
        if isinstance(contraido, bool):
            contraido_value = contraido
        elif isinstance(contraido, int):
            contraido_value = contraido
        else:
            # Fallback: convert float to int if needed, otherwise to bool
            if isinstance(contraido, float):
                # Convert float like 1.0 to int 1, or 0.0 to int 0
                contraido_value = int(contraido)
            else:
                contraido_value = bool(contraido)

        # Extract proyecto (same name as before)
        proyecto = aplicacion.get('proyecto', False)

        # Extract year (new field)
        year = aplicacion.get('year', '')

        # Get cuenta from mapping
        cuenta = partidas_cuentaPG.get(economica, '000')

        aplicaciones.append({
            'partida': economica,  # Keep internal name as 'partida' for SICAL compatibility
            'importe': importe,
            'contraido': contraido_value,
            'proyecto': proyecto,
            'year': year,
            'cuenta': cuenta,
            'otro': False,
            'base_imponible': aplicacion.get('base_imponible', 0.0),
            'tipo': aplicacion.get('tipo', 0.0),
            'cuenta_pgp': aplicacion.get('cuenta_pgp', '')
        })

    return aplicaciones

def setup_sical_window(window_manager: SicalWindowManager) -> bool:
    """Setup SICAL window for operation"""
    rama_arqueo = ('TESORERIA', 'GESTION DE COBROS', 'ARQUEOS. APLICACION DIRECTA',
                   'TRATAMIENTO INDIVIDUALIZADO/RESUMEN')
    
    if not abrir_ventana_opcion_en_menu(rama_arqueo):
        return False
    
    window_manager.ventana_arqueo = window_manager.find_arqueo_window()
    return bool(window_manager.ventana_arqueo)

def process_arqueo_operation(ventana_arqueo, datos_arqueo: Dict[str, Any],
                           result: OperationResult) -> OperationResult:
    """Process the arqueo operation in SICAL"""
    arqueo_logger.info('Processing arqueo operation...')
    finalizar_operacion = datos_arqueo.get('finalizar_operacion', False)

    arqueo_logger.info(f'Finalizar operation flag: {finalizar_operacion}')

    try:
        # Phase 1: Initialize form and fill data
        # Note: Duplicate check is now performed in operacion_arqueo() before opening this window
        arqueo_logger.debug('Initializing form and filling data')
        ventana_arqueo.find('path:"2|4"').click()  # New button
        ventana_arqueo.find('class:"TButton" and path:"1|2"').click()  # Confirm

        # Fill main data
        arqueo_logger.warning('Trying to filling data')
        fill_main_panel_data(ventana_arqueo, datos_arqueo, result)
        arqueo_logger.warning('finished to filling data') 
        arqueo_logger.warning(f'result status: {str(result.status)}')

        if result.status != OperationStatus.FAILED:
            result.status = OperationStatus.COMPLETED

        # Phase 2: Validate and finalize if requested
        if result.status == OperationStatus.COMPLETED and finalizar_operacion:
            arqueo_logger.info('Validating and finalizing operation')

            # Validate operation
            if TASK_CALLBACK:
                TASK_CALLBACK('step', step='Validating operation')
            result = validate_operation(ventana_arqueo, result)

            # Print document if validation succeeded
            if result.status == OperationStatus.COMPLETED:
                if TASK_CALLBACK:
                    TASK_CALLBACK('step', step='Printing operation document')
                result = print_operation_document(ventana_arqueo, result)
        else:
            arqueo_logger.debug('Operation filled but not finalized (no _FIN suffix)')

    except Exception as e:
        arqueo_logger.exception('Error in process_arqueo_operation')
        result.status = OperationStatus.FAILED
        result.error = str(e)

    return result

def abrir_ventana_opcion_en_menu(menu_a_buscar):
    '''Selecciona la opción de menu elegida, desplegando cada elemento de
    la rama correspondiente definida mediante una tupla y haciendo doble click 
    en el último de la tupla, que correspondería dicha opción'''

    rama_ado = ('GASTOS', 'OPERACIONES DE PRESUPUESTO CORRIENTE')
    rama_arqueo = ('TESORERIA', 'GESTION DE COBROS', 'ARQUEOS. APLICACION DIRECTA', 
                   'TRATAMIENTO INDIVIDUALIZADO/RESUMEN')
    rama_tesoreria_pagos = ('TESORERIA', 'GESTION DE PAGOS', 'PROCESO DE ORDENACION Y PAGO')

    app = windows.find_window('regex:.*FMenuSical', raise_error=False)
    if not app:
        arqueo_logger.error('SICAL main menu window not found - application may be closed')
        return False

    if not menu_a_buscar:
        menu_a_buscar = rama_arqueo

    retraer_todos_elementos_del_menu()
    
    for element in menu_a_buscar[:-1]:
        element = app.find(f'control:"TreeItemControl" and name:"{element}"', timeout=0.05)
        element.send_keys(keys='{ADD}', wait_time=0.01)

    last_element = menu_a_buscar[-1]
    app.find(f'control:"TreeItemControl" and name:"{last_element}"').double_click()
    return True

@task
def retraer_todos_elementos_del_menu():
    '''Repliega todos los elementos del menu'''
    # Initialize COM for Windows UI Automation if called independently
    try:
        comtypes.CoInitialize()
        com_initialized = True
    except OSError:
        # COM already initialized (e.g., when called from operacion_arqueo)
        com_initialized = False

    try:
        tree_elements = ['GASTOS', 'INGRESOS', 'OPERACIONES NO PRESUPUESTARIAS', 'TESORERIA',
                         'CONTABILIDAD GENERAL', 'TERCEROS', 'GASTOS CON FINANCIACION AFECTADA \ PROYECTO',
                         'PAGOS A JUSTIFICAR Y ANTICIPOS DE CAJA FIJA', 'ADMINISTRACION DEL SISTEMA',
                         'TRANSACCIONES ESPECIALES', 'CONSULTAS AVANZADAS', 'FACTURAS',
                         'OFICINA DE PRESUPUESTO', 'INVENTARIO CONTABLE']

        app = windows.find_window('regex:.*FMenuSical')
        for element in tree_elements:
            element = app.find(f'control:"TreeItemControl" and name:"{element}"',
                               search_depth=2, timeout=0.01)
            #element.send_keys(keys='{ADD}')
            element.send_keys(keys='{SUBTRACT}', wait_time=0.01)
    finally:
        # Only uninitialize if we initialized it in this function
        if com_initialized:
            try:
                comtypes.CoUninitialize()
            except Exception as e:
                arqueo_logger.warning(f"Error uninitializing COM: {e}")


def fill_main_panel_data(ventana_arqueo, datos_arqueo: Dict[str, Any], result: OperationResult) -> OperationResult:
    """Fill the main panel data in SICAL form"""
    # Implementation of filling main panel data
    # (Keeping existing logic but with improved error handling)
    try:
        default_wait_time = 0.02
        ## HACER CLICK EN BOTON NUEVO PARA INICIALIZAR EL FORMULARIO
        boton_nuevo = ventana_arqueo.find('path:"2|4"')
        boton_nuevo.click()
        boton_confirm = ventana_arqueo.find('class:"TButton" and path:"1|2"')
        boton_confirm.click()

        ## INTRODUCIR DATOS PANEL PRINCIPAL
        fecha_element = ventana_arqueo.find('path:"3|4|10"').double_click()
        fecha_element.send_keys(
            datos_arqueo["fecha"], interval=0.05, wait_time=default_wait_time
        )

        caja_element = ventana_arqueo.find('path:"3|4|8"')
        caja_element.send_keys(datos_arqueo["caja"], wait_time=default_wait_time)

        expediente_element = ventana_arqueo.find('path:"3|4|6"').double_click()
        expediente_element.send_keys(
            datos_arqueo["expediente"], wait_time=default_wait_time
        )

        tercero_element = ventana_arqueo.find('path:"3|4|9"').double_click()
        tercero_element.send_keys(datos_arqueo["tercero"], wait_time=default_wait_time)

        naturaleza_element = ventana_arqueo.find('path:"3|4|5"').click(wait_time=default_wait_time)
        naturaleza_element.send_keys(
            datos_arqueo.get('naturaleza', '4'), wait_time=default_wait_time)
        
        naturaleza_element.send_keys(keys="{Enter}", wait_time=default_wait_time)

        
        
        time.sleep(0.05)
        descripcion_element = ventana_arqueo.find('path:"3|4|7"').double_click()
        descripcion_element.send_keys(keys="{Ctrl}{A}", wait_time=default_wait_time)
        descripcion_element.send_keys(datos_arqueo["resumen"], wait_time=default_wait_time)
        descripcion_element.send_keys(keys="{Enter}", wait_time=default_wait_time)

        ## INTRODUCIR DATOS APLICACIONES CONTABLES

        #aplicaciones_element = ventana_arqueo.find('path:"3|1|1|1"').double_click()
        #grid_element = ventana_arqueo.find('path:"3|1|1|1|1"')
        suma_aplicaciones = 0

        for i, aplicacion in enumerate(datos_arqueo["aplicaciones"]):

            arqueo_logger.info(f"APLICACION debug: {aplicacion} ")

            # Report progress to GUI
            if TASK_CALLBACK:
                partida = aplicacion.get("partida", "N/A")
                importe = aplicacion.get("importe", "0.00")
                line_details = f"Budget: {partida}, Amount: €{importe}"
                TASK_CALLBACK('step',
                            step=f'Processing line item {i+1} of {len(datos_arqueo["aplicaciones"])}',
                            current_line_item=i+1,
                            line_item_details=line_details)

            if (float(aplicacion["importe"].replace(",", ".")) > 0.0):  
                # si el importe de la partida es mayor que cero
                
                new_button_element = ventana_arqueo.find('path:"3|2|2" and class:"TBitBtn"').click()
                naturaleza_operacion =  datos_arqueo.get('naturaleza', '4')

                if datos_arqueo.get('naturaleza') == '4':
                    ventana_arqueo.send_keys(
                        keys=aplicacion["partida"],
                        interval=0.01,
                        wait_time=default_wait_time,
                        send_enter=False,
                    )

                    if not aplicacion.get("contraido", False):
                    # Code runs if "contraido" doesn't exist or has any falsy value:
                        time.sleep(0.2)
                        ventana_arqueo.send_keys(
                            keys="{Tab}{Tab}{Tab}", wait_time=default_wait_time, interval=0.1
                        )
                        ventana_arqueo.send_keys(
                            keys=aplicacion["importe"],
                            interval=0.1,
                            wait_time=default_wait_time,
                            send_enter=False,
                        )
                        #hacemos enter para aceptar la casilla cuenta
                        ventana_arqueo.send_keys(keys="{Enter}", wait_time=0.02)
                        check_button_element = ventana_arqueo.find('path:"3|2|4"').click()
                        suma_aplicaciones = suma_aplicaciones + float(
                            aplicacion["importe"].replace(",", ".")
                        )

                elif (naturaleza_operacion == '5'):
                    ventana_arqueo.send_keys(
                        keys=aplicacion["partida"],
                        interval=0.01,
                        wait_time=default_wait_time,
                        send_enter=False,
                    )
                    _contraido = aplicacion.get("contraido", False)
                    if not _contraido:
                        arqueo_logger.info("NATURALEZA 5, not contraido. SEND ADITIONAL SEND KEYs")
                        ventana_arqueo.send_keys(keys="{Tab}", wait_time=0.02, interval=0.02)
                    else:
                        arqueo_logger.info(f"VALOR DEL CONTRAIDO: {_contraido}")
                        #NOS POSICIONAMOS EN LA CELDA CONTRAIDO
                        time.sleep(1)
                        arqueo_logger.info(f"enviamos TAB PARA POSICIONARNOS EN CONTRAIDO")
                        ventana_arqueo.send_keys(keys="{Tab}", wait_time=0.02, interval=0.02)
                        time.sleep(1)

                        if clean_value(_contraido) == True: #nuevo contraido
                            # tenemos que enviar las siguientes teclas "({Alt}{Down} x 2) + {Fin} + {Enter}"
                            arqueo_logger.critical(f"tenemos que enviar combinacion teclado para nuevo contraido ")
                            arqueo_logger.critical(f"enviamos primer ALT + DOWN")
                            ventana_arqueo.send_keys(keys="{Alt}{Down}", wait_time=1 )
                            arqueo_logger.critical(f"enviamos SEGUNDO ALT + DOWN")
                            #ventana_arqueo.send_keys(keys="{Alt}{Down}", wait_time=4 )
                            arqueo_logger.critical(f"enviamos END")
                            ventana_arqueo.send_keys(keys="{End}", wait_time=1 )
                            arqueo_logger.critical(f"enviamos ENTER")
                            ventana_arqueo.send_keys(keys="{Enter}", wait_time=1 )
                        else: #~contraido existente
                            arqueo_logger.critical(f"contraido existente, escribimos su valor")
                            ventana_arqueo.send_keys(keys=_contraido)
                            arqueo_logger.info(f"TODO;: PROCESS CONTRAIDO.....{aplicacion.get('contraido', 'sin contraido')}")

                    ventana_arqueo.send_keys(keys="{Tab}{Tab}{Tab}", wait_time=0.02, interval=0.02)
                    ventana_arqueo.send_keys(
                        keys=aplicacion["importe"],
                        interval=0.02,
                        wait_time=0.02,
                        send_enter=False,
                    )
                    #hacemos enter para aceptar la casilla cuenta
                    ventana_arqueo.send_keys(keys="{Enter}", wait_time=0.02)
                    check_button_element = ventana_arqueo.find('path:"3|2|4"').click()
                    suma_aplicaciones = suma_aplicaciones + float(
                        aplicacion["importe"].replace(",", ".")
                    )

                else: 
                    arqueo_logger.info(f"otra NATURALEZA ?? ... {naturaleza_operacion} ")   
                
        total_aplicaciones = ventana_arqueo.find('path:"3|3|1"').get_value().replace(",", ".")

        result.total_operacion = total_aplicaciones
        result.suma_aplicaciones = suma_aplicaciones
        

    except Exception as e:
        arqueo_logger.critical("Exception fillling operation data")
        arqueo_logger
        result.status = OperationStatus.FAILED
        result.error = f"Validation error: {str(e)}"
    
    return result
        

def process_aplicaciones(ventana_arqueo, aplicaciones: list, 
                        result: OperationResult) -> OperationResult:
    """Process aplicaciones in SICAL form"""
    # Implementation of processing aplicaciones
    # (Keeping existing logic but with improved error handling)
    pass

def validate_operation(ventana_arqueo, result: OperationResult) -> OperationResult:
    """Validate the operation in SICAL"""
    try:
        ventana_arqueo.find('name:"Validar" and path:"2|7"').click()
        ventana_arqueo.find('class:"TButton" and name:"Yes" and path:"1|2"').click()
        ventana_arqueo.find('class:"TButton" and name:"OK" and path:"1|1"').click()
        
        num_operacion = ventana_arqueo.find('class:"TEdit" and path:"3|4|14"').get_value()
        result.num_operacion = num_operacion
        
    except Exception as e:
        result.status = OperationStatus.FAILED
        result.error = f"Validation error: {str(e)}"
    
    return result

def print_operation_document(ventana_arqueo, result: OperationResult) -> OperationResult:
    """Print TALÓN DE CARGO in SICAL"""
    try:
        ventana_arqueo.find('class:"TBitBtn" and name:"Documento" and path:"2|3"').click()
        time.sleep(3) # Wait for Seleccion Tipo doc to load
        ventana_seleccion_tipo_doc = windows.find_window('regex:.*FseleccionTipoDoc')
        ventana_seleccion_tipo_doc.find('class:"TCheckBox" and path:"1|3" and name:"Talón de Cargo"').click()
        time.sleep(0.05)
        #deseleccionar carta de pago y seleccionar talón de cargo
        ventana_seleccion_tipo_doc.find('class:"TCheckBox" and path:"1|4"').click()
        time.sleep(0.05)
        ventana_seleccion_tipo_doc.find('class:"TButton" and name:"OK" and path:"1|2"').click()
        time.sleep(1)

        #imprimir y guardar como pdf
        ventana_visualizador_documentos = windows.find_window('regex:.*Visualizador de Documentos de SICAL v2')
        boton_imprimir_click = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|6"').click()
        time.sleep(0.1)
        boton_salir_click = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|5"').click()
        #boton_guardar_pdf = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|2"').click()
        result.status = OperationStatus.COMPLETED
        return result
    
    except Exception as e:
        result.status = OperationStatus.INCOMPLETED
        result.error = f"Print document error: {str(e)}"
    return result

def handle_error_cleanup(ventana_arqueo):
    """Clean up SICAL windows in case of error"""
    try:
        modal_dialog = windows.find_window("regex:.*mtec40")
        if modal_dialog:
            modal_dialog.find('class:"TButton" and name:"OK"').click()
        
        # Additional cleanup as needed
    except Exception as e:
        arqueo_logger.exception("Error during cleanup: %s", str(e))