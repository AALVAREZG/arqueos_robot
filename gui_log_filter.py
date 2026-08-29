"""
Filtro de la ventana de registro: solo lo nuestro.

**Por que una lista blanca y no una negra.** El problema no es «robocorp habla
mucho»: es que el entorno arrastra decenas de bibliotecas con logger propio.
Solo `fontTools` trae unos veinte (`fontTools.varLib`, `fontTools.subset`,
`fontTools.ttLib.woff2`...), y a su lado estan `RPA.Desktop`,
`RobotFramework`, `WDM`, `comtypes`, `charset_normalizer`, `urllib3`, `PIL`,
`pika`, `asyncio`... Una lista negra hay que ampliarla cada vez que aparece
una biblioteca nueva, y mientras tanto la ventana se llena y empuja fuera lo
unico que el operador estaba mirando. Con lista blanca, una biblioteca nueva
no puede colarse: simplemente no esta.

El precio es el simetrico: un modulo NUESTRO que no este en la lista no se ve.
Por eso la lista se deriva de los ficheros del proyecto y esta aqui al lado de
ellos — si se anade un modulo, se anade aqui.

El filtro se pone **solo en el manejador de la ventana**. La consola y el
fichero de registro siguen recibiendolo todo: cuando hay que depurar de verdad,
el ruido de terceros es justamente lo que se quiere leer.
"""

import logging

# Raices de logger propias. Un logger cuenta como nuestro si su primer
# componente (lo anterior al primer punto) esta aqui: asi `sical.consumer` entra
# por `sical`, y `processors.ado220_processor` por `processors`.
OWN_LOGGERS = frozenset({
    '__main__',
    # Modulos del proyecto (get_logger(__name__) de logging_setup)
    'arqueo_task_consumer',
    'arqueo_tasks',
    'arqueos_gui',
    'config',
    'document_mode',
    'logging_setup',
    'rabbit_heartbeat',
    'run_trace',
    'sical_security',
    'sical_ui_utils',
    'status_manager',
    'task_history_db',
    # Paquetes del proyecto
    'doc_pipeline',
})


class OwnCodeFilter(logging.Filter):
    """Deja pasar solo los registros emitidos por codigo del proyecto."""

    def filter(self, record):
        return record.name.split('.', 1)[0] in OWN_LOGGERS


def install(handler, level=logging.INFO):
    """
    Prepara un manejador para la ventana de registro: nivel y filtro.

    Devuelve el mismo manejador, para poder encadenar.
    """
    handler.setLevel(level)
    handler.addFilter(OwnCodeFilter())
    return handler
