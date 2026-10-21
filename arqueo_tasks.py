# Standard library imports
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
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

# Latido a RabbitMQ (spec §6.3). Va en una ranura APARTE de TASK_CALLBACK, no
# compartiendola: la GUI registra la suya en arqueos_gui.py y el consumidor
# registra el latido, y con una sola ranura el ultimo en llegar borraba al
# otro. Dos ranuras y un unico `notify_step` que llama a las dos.
HEARTBEAT_CALLBACK: Optional[Callable] = None


def set_task_callback(callback: Optional[Callable] = None):
    """Set the task callback function for GUI integration."""
    global TASK_CALLBACK
    TASK_CALLBACK = callback


def set_heartbeat_callback(callback: Optional[Callable] = None):
    """Registra el publicador de latidos del consumidor."""
    global HEARTBEAT_CALLBACK
    HEARTBEAT_CALLBACK = callback


# Marca del paso anterior, para poder decir cuanto tardo cada uno.
_ultimo_paso = {'t': None, 'nombre': None}


def notify_step(step: str, **kwargs) -> None:
    """
    Un paso del robot: a la GUI local, a RabbitMQ y al rastro en disco.

    Publicarlo da tres cosas de golpe (spec §6.3): el timeout por silencio
    -que deja de matar tareas vivas-, el progreso real en el Task Monitor y
    los tiempos por fase en vivo. Nunca lanza: un latido perdido no puede
    tumbar una operacion contable.

    En el rastro cada paso lleva **cuanto tardo el anterior**. Es lo que
    convierte una lista de pasos en un diagnostico: sin esa cifra se ve que el
    robot llego hasta cierto punto, con ella se ve donde se quedo parado.
    """
    ahora = time.time()
    previo = _ultimo_paso['t']
    run_trace.event(
        'step', step=step,
        paso_anterior=_ultimo_paso['nombre'],
        segundos_del_anterior=None if previo is None else round(ahora - previo, 3),
        **kwargs)
    _ultimo_paso['t'] = ahora
    _ultimo_paso['nombre'] = step

    if TASK_CALLBACK:
        try:
            TASK_CALLBACK('step', step=step, **kwargs)
        except Exception:  # noqa: BLE001
            pass
    if HEARTBEAT_CALLBACK:
        try:
            HEARTBEAT_CALLBACK(step, **kwargs)
        except Exception:  # noqa: BLE001
            pass


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


# Modo de documento: lo decide el productor y viaja en el mensaje (spec §4).
import document_mode
import run_trace

# Centralized phase-oriented logging (see logging_setup.py).
from logging_setup import (
    get_logger, configure_logging, phase as log_phase, ok as log_ok,
    warn as log_warn, fail as log_fail, detail as log_detail,
)

configure_logging()  # idempotent; entrypoints may also call it
arqueo_logger = get_logger(__name__)

# Finalization flag constant
FINALIZE_SUFFIX = '_FIN'

from sical_ui_utils import wait_for_window

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
                'similiar_records_encountered': obj.similiar_records_encountered,
                'duplicate_details': obj.duplicate_details,
                'duplicate_check_metadata': obj.duplicate_check_metadata,
                'duplicate_confirmation_token': obj.duplicate_confirmation_token,
                'duplicate_token_expires_at': obj.duplicate_token_expires_at,
                'capture_status': obj.capture_status,
                'capture_error': obj.capture_error
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
    # Duplicate detection details (populated when status is P_DUPLICATED)
    duplicate_details: Optional[list] = field(default_factory=list)
    duplicate_check_metadata: Optional[dict] = field(default_factory=dict)
    # Confirmation token the producer must send back to force_create. Without
    # these two fields sical-robot has nothing to store, and its "Confirm
    # duplicate" action fails with "No duplicate confirmation token found".
    duplicate_confirmation_token: Optional[str] = None
    duplicate_token_expires_at: Optional[float] = None
    # Attachment-finalization ack (None when the task carried no attachment).
    # Contable-document capture ack (spec v2). The captured PDF itself is
    # carried out-of-band on the result message, not in this dataclass.
    capture_status: Optional[str] = None  # 'CAPTURED' | 'FAILED'
    capture_error: Optional[str] = None

class SicalWindowManager:
    def __init__(self):
        self.ventana_arqueo = None

    def find_arqueo_window(self, timeout: float = 5.0):
        return wait_for_window(SICAL_WINDOWS['arqueo'], timeout=timeout)

    def close_window(self):
        if self.ventana_arqueo:
            try:
                boton_cerrar = self.ventana_arqueo.find('name:"Cerrar"', search_depth=8, raise_error=False)
                if boton_cerrar:
                    boton_cerrar.click()
                    self.ventana_arqueo.find('class:"TButton" and name:"No"').click()
            except Exception as e:
                arqueo_logger.exception("Error closing window: %s", str(e))

def _validate_force_create(operation_data: Dict[str, Any],
                           detalle: Dict[str, Any],
                           result: OperationResult) -> OperationResult:
    """
    Validate a force_create request before opening any SICAL window.

    force_create means the duplicate check is deliberately skipped, so it is
    only honoured when accompanied by a valid single-use token issued by a
    prior Phase 1 check on this same operation. An invalid or missing token
    fails the operation rather than silently falling back to creating it.

    Args:
        operation_data: Full operation dict (carries the token at its root)
        detalle: The untransformed operation detail the token is bound to
        result: Current operation result

    Returns:
        The result, set to FAILED when validation does not pass
    """
    from sical_security import get_confirmation_manager, audit_log_force_create

    token_id = operation_data.get('duplicate_confirmation_token')

    is_valid, error_msg = get_confirmation_manager().validate_token(token_id, detalle)
    audit_log_force_create({**detalle,
                            'duplicate_confirmation_token': token_id},
                           is_valid, error_msg)

    if not is_valid:
        log_fail(arqueo_logger, 'SECURITY', f'invalid force_create: {error_msg}')
        result.status = OperationStatus.FAILED
        result.error = f'Security validation failed: {error_msg}'
        return result

    return result


# =============================================================================
# CAMPOS DE FECHA DE LA VENTANA DE FILTROS (FilOpera)
# =============================================================================
#
# SICAL valida el rango al salir de `fecha_desde`: si la fecha que se escribe
# es POSTERIOR a la `fecha_hasta` que el campo ya tenia, levanta un modal de
# Error y bloquea la consulta. Y ese modal se cuela como hijo 1 de la ventana,
# desplazando todos los `path:"2|N"` a `3|N`, asi que la busqueda siguiente
# (justamente `fecha_hasta`, 2|17) agota 10 s y se reporta un `path` en vez
# del mensaje de SICAL. Ocho de los nueve fallos del 31/08/2026 son eso.
#
# La condicion se cumple porque FilOpera se REUTILIZA: cuando la tarea
# anterior la deja abierta, los dos campos conservan su fecha.
#
# Reordenar los campos no vale: escribir `hasta` primero deja el `desde`
# viejo comparandose contra el `hasta` nuevo, y falla igual en el caso
# simetrico (fecha nueva anterior a la que habia).
#
# Y VACIAR los campos tampoco es una salida: `{Ctrl}a` no lo procesa un
# TMaskEdit de Delphi (solo funciona en campos de texto corrientes), asi que
# no hay forma fiable de dejarlos en blanco por teclado.
#
# La salida es ENSANCHAR PRIMERO Y ESTRECHAR DESPUES, que no necesita vaciar
# nada y es correcta venga la fecha nueva por delante o por detras:
#
#   1. `hasta` = 31/12/2099   -> cualquier `desde` heredado es <= ese tope
#   2. `desde` = fecha        -> <= 31/12/2099
#   3. `hasta` = fecha        -> == `desde`
#
# En ningun paso el `desde` supera al `hasta`, asi que la validacion no
# dispara. La escritura en si va con ocho retrocesos por delante, que es lo
# unico que deja el cursor en la primera posicion de la mascara; ver
# `_escribir_fecha`.


def _fecha_solo_digitos(fecha: Any, etiqueta: str) -> str:
    """Normaliza a los 8 digitos DDMMAAAA que espera la mascara.

    El productor ya publica la fecha sin barras (`sanitizeArqueoFecha`), asi
    que esto es cinturon: si algun dia vuelve a llegar con separadores por un
    camino nuevo, se para aqui con el valor delante en vez de mascarse contra
    la mascara.
    """
    digitos = re.sub(r'\D', '', str(fecha if fecha is not None else ''))
    if len(digitos) != 8:
        raise ValueError(
            f'{etiqueta}: se esperaban 8 digitos DDMMAAAA y llego "{fecha}"')
    return digitos


def _fecha_con_barras(digitos: str) -> str:
    """DDMMAAAA -> DD/MM/AAAA, que es como lo devuelve el campo al leerlo."""
    return f'{digitos[0:2]}/{digitos[2:4]}/{digitos[4:8]}'


# Tope superior provisional del paso 1. Cualquier fecha de un arqueo real es
# anterior, que es lo unico que se le pide.
FECHA_TOPE_SUPERIOR = '31122099'

# Ocho retrocesos: una por cada posicion de digito de la mascara DD/MM/AAAA.
# Se construye repitiendo `{BACK}` en vez de usar la forma con contador
# (`{BACK 8}`) para no depender de como la parsea la libreria.
BORRAR_CAMPO_FECHA = '{BACK}' * 8


def _misma_fecha(leido: Optional[str], digitos: str) -> Optional[bool]:
    """Compara lo leido del campo con la fecha pedida, por COMPONENTES.

    SICAL rellena los grupos con espacios, no con ceros: al salir del campo
    deja "20/ 7/2026", que es exactamente 20/07/2026. Comparar quitando los
    no-digitos daba "2072026" -- siete digitos -- y no igualaba nunca, asi que
    la comprobacion rechazaba fechas perfectamente escritas.

    Devuelve None cuando lo leido no se puede interpretar, para que quien
    llame lo acepte en vez de tumbar la operacion.
    """
    partes = [p.strip() for p in (leido or '').split('/')]
    if len(partes) != 3 or not all(p.isdigit() for p in partes):
        return None
    dia, mes, anio = (int(p) for p in partes)
    return (dia, mes, anio) == (int(digitos[0:2]), int(digitos[2:4]),
                                int(digitos[4:8]))


def _escribir_fecha(campo, digitos: str, etiqueta: str, wait_time: float) -> None:
    """Escribe la fecha y comprueba que el campo quedo con ella.

    La comprobacion no bloquea cuando el campo no se puede LEER (get_value
    devuelve None o vacio): distinguir "no legible" de "vacio" no es posible,
    y tumbar una operacion buena por no poder leer un campo seria peor que el
    fallo del que protege. Mismo criterio que `nombra_operacion` en la captura
    de contables. Solo se falla cuando se lee un valor y discrepa.
    """
    esperado = _fecha_con_barras(digitos)

    for intento in (1, 2):
        # Ocho retrocesos y luego los ocho digitos.
        #
        # Los retrocesos borran hacia atras y arrastran el cursor con ellos,
        # asi que ocho -- las posiciones de digito de la mascara -- lo dejan
        # en la primera, caiga el clic donde caiga. Es lo unico que asegura
        # que lo que se escriba empiece por el principio.
        #
        # Las tres alternativas ya se probaron y ninguna sirve en este
        # control:
        #   - `double_click()`: selecciona SOLO una parte del campo, asi que
        #     los digitos entran por un punto medio.
        #   - `{Ctrl}a`: un TMaskEdit de Delphi no lo procesa.
        #   - `{Home}`: la mascara se come el `0` inicial del mes. Medido el
        #     01/09/2026 -- pidiendo 20/07/2026 el campo quedaba en
        #     "20/ 7/2026", dos intentos seguidos.
        campo.click()
        campo.send_keys(BORRAR_CAMPO_FECHA, interval=0.01, wait_time=wait_time)
        campo.send_keys(digitos, interval=0.01, wait_time=wait_time,
                        send_enter=True)

        try:
            leido = campo.get_value()
        except Exception as e:  # noqa: BLE001 - leer no debe tumbar la tarea
            log_warn(arqueo_logger, 'DUP-CHECK',
                     f'{etiqueta}: no se pudo leer el campo ({e}); se acepta')
            return

        coincide = _misma_fecha(leido, digitos)

        if coincide:
            return

        if coincide is None:
            log_warn(arqueo_logger, 'DUP-CHECK',
                     f'{etiqueta}: no se pudo interpretar "{leido}" tras '
                     f'escribir {esperado}; se acepta y sigue')
            return

        log_warn(arqueo_logger, 'DUP-CHECK',
                 f'{etiqueta}: quedo "{leido}" y se pedia "{esperado}" '
                 f'(intento {intento})')

    raise ValueError(
        f'{etiqueta}: no se pudo escribir {esperado} en el campo de fecha')


# =============================================================================
# CICLO DE VIDA DE ConOpera / FilOpera
# =============================================================================
#
# `arqueos_robot` reutilizaba la ConOpera que encontrara abierta
# ('Consulta window already open, reusing') y no cerraba nada al fallar, asi
# que una tarea heredaba la ventana de la anterior: sus campos con la fecha
# vieja, y a veces un modal de Error encima. Con el modal, todos los
# `path:"2|N"` se desplazan a `3|N` y la busqueda siguiente agota 10 s.
#
# `gastos_robot` no tiene el problema porque abre ConOpera SIEMPRE desde el
# menu (`_setup_consulta_window` llama a `open_menu_option` sin condicion) y
# la cierra al terminar. Se adopta lo mismo, mas un `finally` para que un
# fallo tampoco deje nada abierto: sin el, un fallo envenena a la siguiente y
# la cadena no se corta sola.


def _despachar_modales(ventana, intentos: int = 3) -> int:
    """Cierra los modales que haya encima de `ventana`. Devuelve cuantos.

    Se registra el texto porque es lo unico que dice POR QUE SICAL rechazo
    algo; sin esto el fallo llega como un `path` inexistente y no hay forma de
    saber que paso.
    """
    cerrados = 0
    for _ in range(intentos):
        modal = ventana.find('class:"TMessageForm"', timeout=0,
                             raise_error=False)
        if not modal:
            break

        texto = ''
        try:
            for hijo in modal.iter_children(max_depth=3):
                nombre = (hijo.name or '').strip()
                if nombre and nombre not in ('OK', 'Cerrar', 'Yes', 'No'):
                    texto = nombre
                    break
        except Exception:  # noqa: BLE001 - leer el texto no debe tumbar nada
            pass

        boton = (modal.find('class:"TButton" and name:"OK"', timeout=0.3,
                            raise_error=False)
                 or modal.find('class:"TButton"', timeout=0.3,
                               raise_error=False))
        if not boton:
            break

        log_warn(arqueo_logger, 'DUP-CHECK',
                 'modal de SICAL descartado: ' + (texto or '(sin texto)'))
        try:
            boton.click()
        except Exception:  # noqa: BLE001
            break
        cerrados += 1
        time.sleep(0.2)

    return cerrados


def _ventana_abierta(patron: str):
    """La ventana si esta abierta AHORA, sin esperar; si no, None.

    `wait_for_window` sirve para esperar a que una ventana aparezca: usada para
    comprobar que NO esta, agota su plazo entero cada vez (medido: 1,6 s para
    comprobar dos ventanas que no estaban).
    """
    try:
        vs = windows.find_windows(patron, timeout=0)
    except Exception:  # noqa: BLE001
        return None
    return vs[0] if vs else None


def _esperar_cierre(ventana, patron: str, timeout: float) -> bool:
    """Espera a que la ventana desaparezca, contestando No si SICAL pregunta.

    Vuelve en cuanto la ventana se va, en vez de agotar un plazo fijo.
    """
    fin = time.monotonic() + timeout
    while True:
        if not _ventana_abierta(patron):
            return True
        try:
            conf = ventana.find('class:"TButton" and name:"No"', timeout=0,
                                raise_error=False)
            if conf:
                conf.click()
        except Exception:  # noqa: BLE001 - la ventana puede irse a mitad
            pass
        if time.monotonic() >= fin:
            return False
        time.sleep(0.1)


def _cerrar_ventana_sical(patron: str, etiqueta: str, fase: str = 'DUP-CHECK') -> bool:
    """Cierra la ventana si esta abierta y COMPRUEBA que se fue.

    Comprobarlo importa: el localizador `name:"Cerrar"` es ambiguo -- con un
    modal encima hay dos, el de la barra de titulo del modal (primero en orden
    de arbol) y el de la ventana --, asi que un click puede cerrar el modal y
    dejar la ventana abierta creyendo que se cerro.
    """
    ventana = _ventana_abierta(patron)
    if not ventana:
        return True

    _despachar_modales(ventana)

    for locator in ('class:"TBitBtn" and name:"Salir"', 'name:"Cerrar"'):
        try:
            boton = ventana.find(locator, search_depth=8, timeout=0.5,
                                 raise_error=False)
        except Exception:  # noqa: BLE001
            boton = None
        if not boton:
            continue

        try:
            boton.click()
        except Exception:  # noqa: BLE001
            continue

        if _esperar_cierre(ventana, patron, timeout=3.0):
            return True

    log_warn(arqueo_logger, fase,
             'no se pudo cerrar la ventana ' + etiqueta)
    return False


def _dejar_sical_sin_ventanas_de_consulta() -> None:
    """Cierra FilOpera y ConOpera, en ese orden (la hija primero)."""
    _cerrar_ventana_sical(SICAL_WINDOWS['filtros'], 'Filtros')
    _cerrar_ventana_sical(SICAL_WINDOWS['consulta'], 'Consulta')


def _check_for_duplicates(datos_arqueo: Dict[str, Any], result: OperationResult,
                          original_data: Optional[Dict[str, Any]] = None) -> OperationResult:
    """
    Check for duplicate operations using the Consulta window.

    When similar records are found the operation is aborted with P_DUPLICATED
    and a confirmation token is issued, so the producer can resend the same
    operation with duplicate_policy='force_create' to override the check.

    Args:
        datos_arqueo: Operation data to search for (transformed for SICAL)
        result: Current operation result
        original_data: The untransformed `detalle` the token is bound to. The
            producer resends this verbatim in Phase 2, so hashing it (rather
            than the transformed copy) keeps validation stable. Falls back to
            datos_arqueo when not supplied.

    Returns:
        Updated operation result with duplicate check status
    """
    log_phase(arqueo_logger, 'DUP-CHECK', 'checking for similar operations')
    notify_step('Checking for duplicate operations')

    try:
        # Punto de partida CONOCIDO: se cierra lo que haya quedado de una
        # tarea anterior en vez de reutilizarlo. Cual localizador resuelve no
        # dice en que estado esta la ventana.
        _dejar_sical_sin_ventanas_de_consulta()

        # Y se abre siempre desde el menu, como hace `gastos_robot`.
        ventana_consulta = None
        for attempt in (1, 2):
            if not abrir_ventana_opcion_en_menu(SICAL_MENU_PATHS['consulta'],
                                                rapido=attempt == 1):
                if attempt == 2:
                    result.status = OperationStatus.FAILED
                    result.error = 'Failed to open Consulta window'
                    return result
                time.sleep(1.0)
                continue

            ventana_consulta = wait_for_window(SICAL_WINDOWS['consulta'], timeout=15.0)
            if ventana_consulta:
                break

            log_warn(arqueo_logger, 'DUP-CHECK',
                     f'Consulta window not found on attempt {attempt}, retrying...')

        if not ventana_consulta:
            result.status = OperationStatus.FAILED
            result.error = 'Consulta window not found after retry'
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

        filtros_window = wait_for_window(SICAL_WINDOWS['filtros'], timeout=15.0)

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

        # Date range (same date for from and to).
        # Se ensancha primero el tope superior y se estrecha al final: ver el
        # bloque de comentarios sobre los campos de fecha, arriba. FilOpera
        # puede llegar reutilizada con la fecha de la tarea anterior, y
        # escribir un `desde` posterior al `hasta` que hay levanta un modal de
        # Error que desplaza todos los localizadores `2|N`.
        fecha = _fecha_solo_digitos(datos_arqueo['fecha'], 'fecha del arqueo')

        from_date_field = filtros_window.find(FILTROS_FORM_PATHS['fecha_desde'])
        to_date_field = filtros_window.find(FILTROS_FORM_PATHS['fecha_hasta'])

        _escribir_fecha(to_date_field, FECHA_TOPE_SUPERIOR,
                        'tope provisional', wait_time)
        _escribir_fecha(from_date_field, fecha, 'fecha desde', wait_time)
        _escribir_fecha(to_date_field, fecha, 'fecha hasta', wait_time)

        # Caja
        caja_field = filtros_window.find(FILTROS_FORM_PATHS['caja'])
        caja_field.click()
        caja_field.send_keys(datos_arqueo['caja'], interval=0.01, wait_time=wait_time, send_enter=True)

        # Total of aplicaciones
        notify_step(f'processing aplicaciones: {datos_arqueo.get("aplicaciones")}')
        
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
                log_warn(arqueo_logger, 'DUP-CHECK', f'{num_registros} similar record(s) found - possible duplicate')
                result.similiar_records_encountered = int(num_registros) if num_registros else 0
            else:
                result.similiar_records_encountered = 1  # At least one found

            # Issue a confirmation token so the producer can override this
            # abort via duplicate_policy='force_create'. Bound to the original
            # (untransformed) data for hash consistency with Phase 2.
            from sical_security import get_confirmation_manager

            token_data = original_data if original_data is not None else datos_arqueo
            token_id, expires_at = get_confirmation_manager().generate_token(token_data)

            result.duplicate_details = []  # SICAL grid extraction not implemented
            result.duplicate_confirmation_token = token_id
            result.duplicate_token_expires_at = expires_at
            result.duplicate_check_metadata = {
                'check_id': datos_arqueo.get('duplicate_check_id'),
                'check_timestamp': datetime.now().isoformat(),
                'search_criteria': {
                    'tercero': datos_arqueo.get('tercero'),
                    'fecha': datos_arqueo.get('fecha'),
                    'caja': datos_arqueo.get('caja'),
                    'importe': total_importe_str,
                },
            }

            result.status = OperationStatus.P_DUPLICATED
            result.error = f'Possible duplicate operation found, similar records: {result.similiar_records_encountered}'

            # Las ventanas las cierra el `finally`, para que el camino de
            # fallo y el de exito no puedan divergir.
            log_warn(arqueo_logger, 'DUP-CHECK', f'aborting (possible duplicate): {result.error}')

        else:
            # No records found - safe to proceed
            result.similiar_records_encountered = 0
            log_ok(arqueo_logger, 'DUP-CHECK', 'no similar records - proceeding')

            # El modal de "sin registros" y las dos ventanas los cierra el
            # `finally`.

    except windows.ElementNotFound as e:
        log_fail(arqueo_logger, 'DUP-CHECK', f'SICAL element not found: {e}')
        result.status = OperationStatus.FAILED
        result.error = f'Duplicate check error: {str(e)}'
    except Exception as e:
        log_fail(arqueo_logger, 'DUP-CHECK', str(e))
        result.status = OperationStatus.FAILED
        result.error = f'Duplicate check error: {str(e)}'
    finally:
        # Pase lo que pase. Un fallo que deja el modal y FilOpera abiertos
        # envenena a la tarea siguiente, y la cadena no se corta sola.
        try:
            _dejar_sical_sin_ventanas_de_consulta()
        except Exception as e:  # noqa: BLE001 - limpiar no cambia el resultado
            log_warn(arqueo_logger, 'DUP-CHECK', 'limpieza de ventanas: ' + str(e))

    return result

@task
def operacion_arqueo(operation_data: Dict[str, Any],
                     task_id: Optional[str] = None,
                     doc_mode: Optional[str] = None) -> OperationResult:
    """
    Process an arqueo operation in SICAL system based on received message data.

    Args:
        operation_data: Dictionary containing the operation details from RabbitMQ message
        task_id: Optional task id (used for logging/correlation).
        doc_mode: Modo de documento pedido por el productor en el mensaje
            (spec §4): 'legacy_print' | 'inline_capture' | 'deferred'. None =
            el mensaje no lo trae y se cae a CONTABLE_CAPTURE_ENABLED, que a
            partir de aqui es reserva y no interruptor.

    Returns:
        OperationResult: Object with operation status. When the contable
        capture flag is ON and the operation is finalized, the captured
        contable PDF envelope is stashed on the result as
        ``result._contable_document`` for the consumer to attach to the
        result message (kept off the dataclass to avoid bloating asdict).
    """
    # NOTE: COM initialization is now handled at the consumer thread level
    # to avoid COM state issues between successive task executions

    log_detail(arqueo_logger, 'PARSED', f'raw operation_data: {operation_data}')
    init_time = datetime.now()
    result = OperationResult(
        status=OperationStatus.PENDING,
        init_time=str(init_time),
        sical_is_open=False
    )

    window_manager = SicalWindowManager()

    try:
        # Prepare operation data
        notify_step('Preparing operation data')

        # Extract tipo and detalle from operation_data
        # operation_data structure: {"tipo": "arqueo", "detalle": {...}}
        operation_type = operation_data.get('tipo', 'arqueo')
        detalle = operation_data.get('detalle', {})

        datos_arqueo = create_arqueo_data(detalle)
        # Duplicate-policy fields travel at the message root, not inside
        # `detalle`; carry them alongside the transformed data so the check has
        # them available.
        duplicate_policy = operation_data.get('duplicate_policy', 'abort_on_duplicate')
        datos_arqueo['duplicate_check_id'] = operation_data.get('duplicate_check_id')
        log_detail(arqueo_logger, 'PARSED', f'type={operation_type} datos_arqueo={datos_arqueo}')

        # Check for duplicates BEFORE opening arqueo window (if finalization flag is set)
        finalizar_operacion = datos_arqueo.get('finalizar_operacion', False)
        if finalizar_operacion:
            if duplicate_policy == 'force_create':
                # Phase 2: the operator already saw the duplicates and confirmed.
                # Validate the token issued in Phase 1 instead of re-checking.
                result = _validate_force_create(operation_data, detalle, result)
                if result.status == OperationStatus.FAILED:
                    log_fail(arqueo_logger, 'DUP-CHECK',
                             'force_create rejected - SICAL window not opened')
                    return result
                log_ok(arqueo_logger, 'DUP-CHECK',
                       'force_create confirmed - skipping duplicate check')
            else:
                result = _check_for_duplicates(datos_arqueo, result, original_data=detalle)

                # If duplicates found or check failed, abort before opening window
                if result.status == OperationStatus.P_DUPLICATED:
                    log_warn(arqueo_logger, 'DUP-CHECK', 'aborting - SICAL window not opened')
                    return result

                if result.status == OperationStatus.FAILED:
                    log_fail(arqueo_logger, 'DUP-CHECK', 'check failed - SICAL window not opened')
                    return result

            # Reset status to continue with operation
            result.status = OperationStatus.PENDING

        # Setup SICAL window
        notify_step('Opening SICAL window')

        if not setup_sical_window(window_manager):
            result.status = OperationStatus.FAILED
            result.error = "Failed to open SICAL window"
            log_fail(arqueo_logger, 'SICAL-OPEN', 'could not open the arqueo window')
            return result
        else:
            result.sical_is_open = True
            result.status = OperationStatus.IN_PROGRESS
            log_ok(arqueo_logger, 'SICAL-OPEN', 'arqueo window open')

        # Process operation (includes validation and printing if _FIN flag is set)
        # Note: Duplicate check is now performed above, before opening the window
        notify_step('Processing arqueo operation')

        result = process_arqueo_operation(window_manager.ventana_arqueo, datos_arqueo,
                                          result, task_id, doc_mode=doc_mode)

        # Sin _FIN o con fallo la ventana se deja abierta para revisarla a mano.
        if result.status == OperationStatus.COMPLETED and finalizar_operacion:
            if _cerrar_ventana_sical(SICAL_WINDOWS['arqueo'], 'Arqueo', fase='CLOSE'):
                log_ok(arqueo_logger, 'CLOSE', 'arqueo window closed')



    except Exception as e:
        log_fail(arqueo_logger, 'FAILED', f'unhandled error in arqueo operation: {e}', exc=True)
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
    """Setup SICAL window for operation.

    The mtec40 arqueo window can take a while to open. Reuse it if already
    open, otherwise open via menu with one retry and a longer wait.
    """
    rama_arqueo = SICAL_MENU_PATHS['arqueo']

    # Reuse the window if it is already open (avoids opening a duplicate
    # session via the menu).
    ventana = _ventana_abierta(SICAL_WINDOWS['arqueo'])
    if ventana:
        log_phase(arqueo_logger, 'SETUP', 'Arqueo (mtec40) window already open, reusing')
        window_manager.ventana_arqueo = ventana
        return True

    for attempt in (1, 2):
        if not abrir_ventana_opcion_en_menu(rama_arqueo, rapido=attempt == 1):
            if attempt == 2:
                return False
            time.sleep(1.0)
            continue

        ventana = window_manager.find_arqueo_window(timeout=15.0)
        if ventana:
            window_manager.ventana_arqueo = ventana
            return True

        log_warn(arqueo_logger, 'SETUP',
                 f'Arqueo (mtec40) window not found on attempt {attempt}, retrying...')

    return False

def process_arqueo_operation(ventana_arqueo, datos_arqueo: Dict[str, Any],
                           result: OperationResult,
                           task_id: Optional[str] = None,
                           doc_mode: Optional[str] = None) -> OperationResult:
    """Process the arqueo operation in SICAL.

    `doc_mode` es el modo de documento que trae el mensaje (spec §4). Llega
    como parametro y no se lee del ambito de `operacion_arqueo`: el bloque de
    finalizacion vive aqui, y darlo por heredado costo una operacion real
    creada en SICAL (26000964) que el productor registro como FALLIDA.
    """
    finalizar_operacion = datos_arqueo.get('finalizar_operacion', False)
    log_detail(arqueo_logger, 'FILL', f'finalizar_operacion={finalizar_operacion}')

    try:
        # Phase 1: Initialize form and fill data
        # Note: Duplicate check is now performed in operacion_arqueo() before opening this window
        log_phase(arqueo_logger, 'FILL', f'writing main panel + {len(datos_arqueo.get("aplicaciones", []))} aplicacion line(s)')
        ventana_arqueo.find('class:"TBitBtn" and name:"Nuevo"').click()  # New button
        ventana_arqueo.find('class:"TButton" and path:"1|2"').click()  # Confirm

        fill_main_panel_data(ventana_arqueo, datos_arqueo, result)

        if result.status != OperationStatus.FAILED:
            result.status = OperationStatus.COMPLETED
            log_ok(arqueo_logger, 'FILL', f'data written (total={result.total_operacion})')
        else:
            log_fail(arqueo_logger, 'FILL', result.error or 'error writing data')

        # Phase 2: Validate and finalize if requested
        if result.status == OperationStatus.COMPLETED and finalizar_operacion:
            # Validate operation
            notify_step('Validating operation')
            result = validate_operation(ventana_arqueo, result)

            # Finalize: lo decide el modo de documento que viene en el
            # mensaje (spec §4); CONTABLE_CAPTURE_ENABLED solo actua de reserva
            # cuando el mensaje no lo trae.
            if result.status == OperationStatus.COMPLETED:
                fallback = _contable_capture_enabled()
                if document_mode.should_capture(doc_mode, fallback):
                    notify_step('Capturing contable document')
                    result = finalize_capture(ventana_arqueo, result, task_id)
                elif document_mode.should_print(doc_mode, fallback):
                    notify_step('Printing operation document')
                    result = print_operation_document(ventana_arqueo, result)
                else:
                    # `deferred`: el robot de operaciones no toca documentos.
                    # El Talon de Cargo queda pendiente y lo encola el
                    # productor. El invariante cambia -COMPLETED ya no implica
                    # que el documento exista- y por eso el atraso tiene que
                    # verse en el Task Monitor (spec §5).
                    log_ok(arqueo_logger, 'CONTABLE',
                           'document_mode=deferred: documento aplazado al robot de documentos')
        else:
            log_ok(arqueo_logger, 'FILL', 'operation filled but not finalized (no _FIN)')

    except Exception as e:
        run_trace.exception('operation_error', e,
                            num_operacion=result.num_operacion)
        log_fail(arqueo_logger, 'FILL', f'error processing operation: {e}', exc=True)
        result.status = OperationStatus.FAILED
        result.error = str(e)

    return result

# Ramas que este robot deja desplegadas a la vez. Medido el 21/10/2026 con
# las dos abiertas: las dos hojas caben en la parte visible del arbol (la de
# Consulta, a ~20 px del borde inferior), asi que cada tarea puede ir directa
# a su hoja. Desplegar solo la propia haria que Consulta y Arqueo se plegaran
# la una a la otra y nunca hubiera atajo.
RAMAS_DEL_ROBOT = ('consulta', 'arqueo')


def _hoja_a_la_vista(app, nombre: str):
    """El item del arbol si esta dentro de la parte visible; si no, None.

    Un item desplegado pero fuera de la zona visible se encuentra igual, y el
    doble clic falla o cae en otro sitio: por eso se mira el rectangulo.
    """
    hoja = app.find(f'control:"TreeItemControl" and name:"{nombre}"',
                    timeout=0, raise_error=False)
    if not hoja:
        return None
    arbol = app.find('control:"TreeControl"', timeout=0, raise_error=False)
    if not arbol:
        return None
    _, top, _, bottom = hoja.rectangle
    _, a_top, _, a_bottom = arbol.rectangle
    return hoja if a_top <= top and bottom <= a_bottom else None


def abrir_ventana_opcion_en_menu(menu_a_buscar, rapido: bool = True):
    '''Abre la opcion de menu `menu_a_buscar` (tupla rama..., hoja).

    Con `rapido`, si la hoja ya esta a la vista se abre con un doble clic sin
    tocar el resto del arbol (medido: ~5 s menos por apertura). Si no, se
    pliega todo y se despliegan las ramas de RAMAS_DEL_ROBOT, para que la
    siguiente apertura si encuentre su hoja a la vista.'''

    app = windows.find_window('regex:.*FMenuSical', raise_error=False, timeout=10.0)
    if not app:
        log_fail(arqueo_logger, 'SICAL-OPEN', 'SICAL main menu window not found - app may be closed')
        return False

    if not menu_a_buscar:
        menu_a_buscar = SICAL_MENU_PATHS['arqueo']

    app.foreground_window()
    hoja = menu_a_buscar[-1]

    if rapido:
        item = _hoja_a_la_vista(app, hoja)
        if item:
            item.double_click()
            return True

    retraer_todos_elementos_del_menu()

    rutas = [SICAL_MENU_PATHS[r] for r in RAMAS_DEL_ROBOT]
    if menu_a_buscar not in rutas:
        rutas.append(menu_a_buscar)
    for ruta in rutas:
        for element in ruta[:-1]:
            element = app.find(f'control:"TreeItemControl" and name:"{element}"', timeout=0.05)
            element.send_keys(keys='{ADD}', wait_time=0.01)

    app.find(f'control:"TreeItemControl" and name:"{hoja}"').double_click()
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


# Desde la actualizacion de SICAL el orden UIA del panel principal cambia al
# editar campos (un TDBEdit salta a la posicion 1 y corre los demas), asi que
# los path posicionales de ese panel no son fiables: se localiza por clase y,
# para los TDBEdit, por columna y fila en pantalla.
_DBEDITS_PANEL = {
    'caja': ('izq', 0),
    'tercero': ('izq', 1),
    'pagos_justificar': ('der', 0),
    'expediente': ('der', 1),
}


def _dbedit_panel(ventana_arqueo, campo: str):
    columna, fila = _DBEDITS_PANEL[campo]
    edits = ventana_arqueo.find_many('class:"TDBEdit"', search_strategy="all")
    xs = [e.rectangle[0] for e in edits]
    if not xs:
        raise RuntimeError('no hay TDBEdit en la ventana de arqueo')
    corte = (min(xs) + max(xs)) / 2
    izq = sorted((e for e in edits if e.rectangle[0] < corte), key=lambda e: e.rectangle[1])
    der = sorted((e for e in edits if e.rectangle[0] >= corte), key=lambda e: e.rectangle[1])
    if len(izq) != 2 or len(der) != 2:
        raise RuntimeError(
            f'disposicion de TDBEdit inesperada ({len(izq)} izq / {len(der)} der): '
            'puede haber un dialogo abierto o SICAL ha cambiado la pantalla')
    return (izq if columna == 'izq' else der)[fila]


def _campo_num_orden(ventana_arqueo):
    edits = ventana_arqueo.find_many('class:"TEdit"', search_strategy="all")
    return min(edits, key=lambda e: e.rectangle[1])


def fill_main_panel_data(ventana_arqueo, datos_arqueo: Dict[str, Any], result: OperationResult) -> OperationResult:
    """Fill the main panel data in SICAL form"""
    # Implementation of filling main panel data
    # (Keeping existing logic but with improved error handling)
    try:
        default_wait_time = 0.02
        ## HACER CLICK EN BOTON NUEVO PARA INICIALIZAR EL FORMULARIO
        boton_nuevo = ventana_arqueo.find('class:"TBitBtn" and name:"Nuevo"')
        boton_nuevo.click()
        boton_confirm = ventana_arqueo.find('class:"TButton" and path:"1|2"')
        boton_confirm.click()

        ## INTRODUCIR DATOS PANEL PRINCIPAL
        fecha_element = ventana_arqueo.find('class:"TDBDateEdit"').double_click()
        fecha_element.send_keys(
            datos_arqueo["fecha"], interval=0.05, wait_time=default_wait_time
        )

        caja_element = _dbedit_panel(ventana_arqueo, 'caja')
        caja_element.send_keys(datos_arqueo["caja"], wait_time=default_wait_time)

        expediente_element = _dbedit_panel(ventana_arqueo, 'expediente').double_click()
        expediente_element.send_keys(
            datos_arqueo["expediente"], wait_time=default_wait_time
        )

        tercero_element = _dbedit_panel(ventana_arqueo, 'tercero').double_click()
        tercero_element.send_keys(datos_arqueo["tercero"], wait_time=default_wait_time)

        naturaleza_element = ventana_arqueo.find('class:"TComboBox"').click(wait_time=default_wait_time)
        naturaleza_element.send_keys(
            datos_arqueo.get('naturaleza', '4'), wait_time=default_wait_time)

        naturaleza_element.send_keys(keys="{Enter}", wait_time=default_wait_time)



        time.sleep(0.05)
        descripcion_element = ventana_arqueo.find('class:"TDBMemo"').double_click()
        descripcion_element.send_keys(keys="{Ctrl}{A}", wait_time=default_wait_time)
        descripcion_element.send_keys(datos_arqueo["resumen"], wait_time=default_wait_time)
        descripcion_element.send_keys(keys="{Enter}", wait_time=default_wait_time)

        ## INTRODUCIR DATOS APLICACIONES CONTABLES

        #aplicaciones_element = ventana_arqueo.find('path:"3|1|1|1"').double_click()
        #grid_element = ventana_arqueo.find('path:"3|1|1|1|1"')
        suma_aplicaciones = 0

        for i, aplicacion in enumerate(datos_arqueo["aplicaciones"]):

            log_detail(arqueo_logger, 'FILL', f'aplicacion[{i}] = {aplicacion}')

            # Report progress to GUI (y a RabbitMQ: cada linea es una noticia
            # mas que rearma la ventana de silencio del productor).
            partida = aplicacion.get("partida", "N/A")
            importe = aplicacion.get("importe", "0.00")
            notify_step(
                f'Processing line item {i+1} of {len(datos_arqueo["aplicaciones"])}',
                current_line_item=i + 1,
                line_item_details=f"Budget: {partida}, Amount: €{importe}")

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
                        log_detail(arqueo_logger, 'FILL', 'naturaleza 5, sin contraido - {Tab}')
                        ventana_arqueo.send_keys(keys="{Tab}", wait_time=0.02, interval=0.02)
                    else:
                        log_detail(arqueo_logger, 'FILL', f'naturaleza 5, contraido={_contraido}')
                        #NOS POSICIONAMOS EN LA CELDA CONTRAIDO
                        time.sleep(1)
                        ventana_arqueo.send_keys(keys="{Tab}", wait_time=0.02, interval=0.02)
                        time.sleep(1)

                        if clean_value(_contraido) == True: #nuevo contraido
                            log_detail(arqueo_logger, 'FILL', 'nuevo contraido: ALT+DOWN, END, ENTER')
                            ventana_arqueo.send_keys(keys="{Alt}{Down}", wait_time=1 )
                            ventana_arqueo.send_keys(keys="{End}", wait_time=1 )
                            ventana_arqueo.send_keys(keys="{Enter}", wait_time=1 )
                        else: #~contraido existente
                            log_detail(arqueo_logger, 'FILL', f'contraido existente: {_contraido}')
                            ventana_arqueo.send_keys(keys=_contraido)

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

                elif (naturaleza_operacion == '2'):
                    ventana_arqueo.send_keys(
                        keys=aplicacion["year"],
                        interval=0.01,
                        wait_time=default_wait_time,
                        send_enter=True,
                    )

                    ventana_arqueo.send_keys(
                        keys=aplicacion["partida"],
                        interval=0.01,
                        wait_time=default_wait_time,
                        send_enter=False,
                    )

                    if aplicacion.get("proyecto", False):
                        ventana_arqueo.send_keys(
                            keys="{Tab}", wait_time=0.02, interval=0.02
                        )
                        ventana_arqueo.send_keys(
                            keys=aplicacion["proyecto"],
                            interval=0.01,
                            wait_time=default_wait_time,
                            send_enter=True,
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
                        #LA NATURALEZA 2 NO ACEPTA el campo cuenta
                        
                        check_button_element = ventana_arqueo.find('path:"3|2|4"').click()
                        suma_aplicaciones = suma_aplicaciones + float(
                            aplicacion["importe"].replace(",", ".")
                        )

                else:
                    log_warn(arqueo_logger, 'FILL', f'unhandled naturaleza: {naturaleza_operacion}')
                
        total_aplicaciones = ventana_arqueo.find('path:"3|3|1"').get_value().replace(",", ".")

        result.total_operacion = total_aplicaciones
        result.suma_aplicaciones = suma_aplicaciones
        

    except Exception as e:
        log_fail(arqueo_logger, 'FILL', f'exception filling operation data: {e}', exc=True)
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
        ventana_arqueo.find('class:"TBitBtn" and name:"Validar"').click()
        ventana_arqueo.find('class:"TButton" and name:"Yes" and path:"1|2"').click()
        ventana_arqueo.find('class:"TButton" and name:"OK" and path:"1|1"').click()

        # Desde la actualizacion de SICAL, tras validar pregunta
        # "Desea Adjuntar Documentacion a la Operacion?"; los documentos van
        # por otro camino, asi que se contesta No.
        dialogo_adjuntar = ventana_arqueo.find(
            'class:"TMessageForm" and name:"Confirm"', timeout=5, raise_error=False)
        if dialogo_adjuntar:
            dialogo_adjuntar.find('class:"TButton" and name:"No"').click()
            log_detail(arqueo_logger, 'VALIDATE', 'dialogo adjuntar documentacion -> No')

        num_operacion = _campo_num_orden(ventana_arqueo).get_value()
        result.num_operacion = num_operacion
        run_trace.event('validated', num_operacion=num_operacion)
        log_ok(arqueo_logger, 'VALIDATE', f'operation validated -> num_operacion={num_operacion}')

    except Exception as e:
        run_trace.exception('validate_error', e)
        log_fail(arqueo_logger, 'VALIDATE', str(e), exc=True)
        result.status = OperationStatus.FAILED
        result.error = f"Validation error: {str(e)}"

    return result

def _contable_capture_enabled() -> bool:
    """
    Consumer-side rollout guard (spec v2). Default False: until this is ON
    the legacy in-app print runs unchanged. Must be ON in tandem with
    sical-robot's contableAssemblyEnabled flag for the new flow to work
    end-to-end.
    """
    try:
        import config
        return bool(getattr(config, 'CONTABLE_CAPTURE_ENABLED', False))
    except Exception:
        return False


def finalize_capture(ventana_arqueo, result: OperationResult,
                     task_id: Optional[str] = None) -> OperationResult:
    """
    Capture the SICAL contable document to a PDF and stash the
    `contable_document` envelope on the result for the consumer to attach
    to the result message. sical-robot does the merge/print/portafirmas.

    The SICAL operation is already committed by validate_operation(), so any
    failure here only sets capture_status -- result.status is NEVER
    regressed (mirrors print_operation_document's "completed whether
    printed or not" semantics).
    """
    try:
        import config
        from doc_pipeline.capture_and_return import capture_and_return
        envelope = capture_and_return(
            ventana_arqueo, result.num_operacion, config)
        result.capture_status = envelope.get('capture_status')
        result.capture_error = envelope.get('capture_error')
        # Out-of-band: not a dataclass field (keeps OperationEncoder small);
        # the consumer reads this via getattr and puts it on the result msg.
        setattr(result, '_contable_document', envelope)
        run_trace.event('contable',
                        via='finalize_capture',
                        num_operacion=result.num_operacion,
                        capture_status=envelope.get('capture_status'),
                        capture_error=envelope.get('capture_error'),
                        sha256=envelope.get('sha256'),
                        size_bytes=envelope.get('size_bytes'),
                        page_count=envelope.get('page_count'),
                        filename=envelope.get('filename'))
        if envelope.get('capture_status') == 'CAPTURED':
            log_ok(arqueo_logger, 'CONTABLE',
                   f"captured {envelope.get('page_count')}p / "
                   f"{envelope.get('size_bytes')} B / "
                   f"sha={(envelope.get('sha256') or '')[:12]} "
                   f"-> returning to producer")
        else:
            log_fail(arqueo_logger, 'CONTABLE',
                     envelope.get('capture_error') or 'capture failed')
    except Exception as e:
        log_fail(arqueo_logger, 'CONTABLE', f'unexpected: {e}', exc=True)
        result.capture_status = 'FAILED'
        result.capture_error = str(e)
        setattr(result, '_contable_document', {
            'capture_status': 'FAILED', 'capture_error': str(e), 'data': None
        })

    # The committed operation stays COMPLETED regardless of capture outcome.
    if result.status != OperationStatus.FAILED:
        result.status = OperationStatus.COMPLETED
    return result


def print_operation_document(ventana_arqueo, result: OperationResult) -> OperationResult:
    """Print TALÓN DE CARGO in SICAL"""
    try:
        # Check if the FseleccionTipoDoc window is already open; only click
        # "Documento" if it isn't, to avoid opening duplicates.
        ventana_seleccion_tipo_doc = wait_for_window(
            'regex:.*FseleccionTipoDoc', timeout=0.5)
        if not ventana_seleccion_tipo_doc:
            ventana_arqueo.find('class:"TBitBtn" and name:"Documento"').click()
            ventana_seleccion_tipo_doc = wait_for_window(
                'regex:.*FseleccionTipoDoc', timeout=15.0)
        if not ventana_seleccion_tipo_doc:
            raise windows.ElementNotFound(
                'FseleccionTipoDoc window did not open within 15s')
        ventana_seleccion_tipo_doc.find('class:"TCheckBox" and path:"1|3" and name:"Talón de Cargo"').click()
        time.sleep(0.05)
        #deseleccionar carta de pago y seleccionar talón de cargo
        ventana_seleccion_tipo_doc.find('class:"TCheckBox" and path:"1|4"').click()
        time.sleep(0.05)
        ventana_seleccion_tipo_doc.find('class:"TButton" and name:"OK" and path:"1|2"').click()
        time.sleep(1)

        #imprimir y guardar como pdf
        ventana_visualizador_documentos = windows.find_window('regex:.*Visualizador de Documentos de SICAL v2')
        boton_imprimir_click = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|7"').click()
        time.sleep(0.1)
        boton_salir_click = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|6"').click()
        #boton_guardar_pdf = ventana_visualizador_documentos.find('class:"TBitBtn" and path:"2|2|2"').click()
        result.status = OperationStatus.COMPLETED
        log_ok(arqueo_logger, 'CONTABLE', 'Talon de Cargo printed in SICAL (legacy in-app)')
        return result

    except Exception as e:
        result.status = OperationStatus.COMPLETED #OPERATION IS COMPLETED although doc iS PRINTER OR NOT
        result.error = f"Print document error: {str(e)}"
        log_warn(arqueo_logger, 'CONTABLE', f'legacy print error (operation still COMPLETED): {e}')
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