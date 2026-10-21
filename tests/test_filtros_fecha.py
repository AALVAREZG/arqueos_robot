# -*- coding: utf-8 -*-
"""Regresion de los campos de fecha de la ventana de filtros (FilOpera).

El 31/08/2026 fallaron 9 arqueos, 8 de ellos exactamente en el mismo sitio: la
busqueda de `fecha_hasta` (`2|17`) justo despues de escribir `fecha_desde`.

La causa: FilOpera se reutiliza, asi que llega con la fecha de la tarea
anterior en los dos campos. SICAL valida el rango al salir de `fecha_desde`,
levanta un modal de Error si la fecha nueva es POSTERIOR a la que hay en
`fecha_hasta`, y ese modal se cuela como hijo 1 desplazando todos los
localizadores `2|N` a `3|N`.

El arreglo es ensanchar el tope superior antes de escribir y estrecharlo al
final. Estas pruebas fijan ese orden, que es lo unico que hace seguros LOS DOS
casos: fecha nueva posterior y fecha nueva anterior a la que habia.
"""

import inspect
import re

import pytest

import arqueo_tasks


class CampoFalso:
    """Sustituto de un elemento robocorp que registra lo que se le hace.

    Modela lo justo de un TMaskEdit: ocho retrocesos dejan el cursor en la
    primera posicion y entonces los ocho digitos entran enteros. NO modela
    `double_click()` (selecciona solo una parte del campo), ni `{Ctrl}a`
    (Delphi no lo procesa), ni `{Home}` + digitos (se come el `0` inicial del
    mes); ninguna prueba debe sugerir que alguna de las tres sirve.
    """

    def __init__(self, valor_inicial='', lecturas=None):
        self.valor = valor_inicial
        self.acciones = []
        # Cola de valores que devolvera get_value(); si se agota se repite el
        # ultimo. None = el campo devuelve su valor real.
        self._lecturas = list(lecturas) if lecturas is not None else None

    def click(self, *a, **k):
        self.acciones.append(('click', None))
        return self

    def send_keys(self, keys=None, **k):
        self.acciones.append(('send_keys', keys))
        if keys == arqueo_tasks.BORRAR_CAMPO_FECHA:
            self._al_principio = True
        elif re.fullmatch(r'\d{8}', keys or ''):
            # Sin haber vuelto al principio, la mascara recibiria los digitos
            # por donde estuviera el cursor: eso es el fallo, no una escritura.
            if getattr(self, '_al_principio', False):
                d = keys
                self.valor = f'{d[0:2]}/{d[2:4]}/{d[4:8]}'
                self._al_principio = False
        return self

    def get_value(self, *a, **k):
        self.acciones.append(('get_value', None))
        if self._lecturas is None:
            return self.valor
        if len(self._lecturas) > 1:
            return self._lecturas.pop(0)
        return self._lecturas[0]

    def escrituras(self):
        return [k for (a, k) in self.acciones if a == 'send_keys']


# ---------------------------------------------------------------------------
# _fecha_solo_digitos
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize('entrada, esperado', [
    ('03072026', '03072026'),
    ('03/07/2026', '03072026'),   # el caso que motivo sanitizeArqueoFecha
    ('03-07-2026', '03072026'),
    (' 03072026 ', '03072026'),
])
def test_normaliza_a_ocho_digitos(entrada, esperado):
    assert arqueo_tasks._fecha_solo_digitos(entrada, 'fecha') == esperado


@pytest.mark.unit
@pytest.mark.parametrize('entrada', ['', None, '0307202', '3/7/2026', 'abc'])
def test_rechaza_lo_que_no_son_ocho_digitos(entrada):
    """No se rellena con ceros: '3/7/2026' son 6 digitos, y adivinar el relleno
    seria inventarse una fecha. Mejor parar nombrando el valor recibido."""
    with pytest.raises(ValueError) as exc:
        arqueo_tasks._fecha_solo_digitos(entrada, 'fecha desde')
    assert 'fecha desde' in str(exc.value)


@pytest.mark.unit
def test_fecha_con_barras():
    assert arqueo_tasks._fecha_con_barras('03072026') == '03/07/2026'


# ---------------------------------------------------------------------------
# _misma_fecha
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize('leido, esperado', [
    ('20/07/2026', True),
    ('20/ 7/2026', True),    # SICAL rellena con ESPACIO, no con cero
    (' 2/ 7/2026', False),
    ('01/07/2026', False),
    (None, None),            # ilegible -> quien llama lo acepta
    ('', None),
    ('  /  /    ', None),
    ('basura', None),
])
def test_compara_por_componentes_no_por_digitos(leido, esperado):
    """Al salir del campo, SICAL deja "20/ 7/2026" -- que ES 20/07/2026.

    Comparar quitando los no-digitos daba "2072026", siete digitos, que no
    iguala nunca a "20072026": la comprobacion rechazaba fechas perfectamente
    escritas y tumbaba la tarea. Medido el 01/09/2026 en sesion limpia.
    """
    assert arqueo_tasks._misma_fecha(leido, '20072026') is esperado


@pytest.mark.unit
def test_el_tope_superior_es_posterior_a_cualquier_arqueo_real():
    tope = arqueo_tasks.FECHA_TOPE_SUPERIOR
    assert arqueo_tasks._fecha_solo_digitos(tope, 'tope') == tope
    from datetime import date
    anio = int(tope[4:8])
    assert anio >= date.today().year + 50, (
        'el tope debe quedar muy por encima de cualquier arqueo real')


# ---------------------------------------------------------------------------
# _escribir_fecha
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_retrocede_al_principio_antes_de_escribir():
    """Ocho retrocesos -- una por posicion de digito -- dejan el cursor en la
    primera, caiga el clic donde caiga. Es lo unico que asegura que los
    digitos entren por el principio."""
    campo = CampoFalso('01/07/2026')
    arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha desde', 0.02)

    assert campo.escrituras() == [arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026']
    assert campo.valor == '03/07/2026'
    assert not any(a == 'double_click' for (a, _) in campo.acciones)


@pytest.mark.unit
def test_son_ocho_retrocesos_uno_por_digito_de_la_mascara():
    assert arqueo_tasks.BORRAR_CAMPO_FECHA.count('{BACK}') == 8
    assert arqueo_tasks.BORRAR_CAMPO_FECHA.replace('{BACK}', '') == ''


@pytest.mark.unit
def test_escribe_una_vez_cuando_el_campo_queda_bien():
    campo = CampoFalso(lecturas=['03/07/2026'])
    arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha desde', 0.02)

    assert campo.escrituras() == [arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026']


@pytest.mark.unit
def test_reintenta_cuando_el_campo_quedo_con_otra_cosa():
    """Primera lectura: lo que habia antes. Segunda: lo pedido."""
    campo = CampoFalso(lecturas=['01/07/2026', '03/07/2026'])
    arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha desde', 0.02)

    assert campo.escrituras() == [arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026',
                                 arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026']


@pytest.mark.unit
def test_falla_si_el_campo_no_acepta_la_fecha():
    campo = CampoFalso(lecturas=['01/07/2026'])
    with pytest.raises(ValueError) as exc:
        arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha hasta', 0.02)

    assert '03/07/2026' in str(exc.value)
    assert 'fecha hasta' in str(exc.value)


@pytest.mark.unit
@pytest.mark.parametrize('lectura', [None, '', '  /  /    '])
def test_no_bloquea_cuando_el_campo_no_se_puede_leer(lectura):
    """Distinguir 'no legible' de 'vacio' no es posible, y tumbar una operacion
    buena por no poder leer un campo seria peor que el fallo del que protege.
    Mismo criterio que nombra_operacion en la captura de contables."""
    campo = CampoFalso(lecturas=[lectura])
    arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha desde', 0.02)

    assert campo.escrituras() == [arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026']


@pytest.mark.unit
def test_no_bloquea_si_get_value_revienta():
    class CampoQueRevienta(CampoFalso):
        def get_value(self, *a, **k):
            raise RuntimeError('no soportado')

    campo = CampoQueRevienta()
    arqueo_tasks._escribir_fecha(campo, '03072026', 'fecha desde', 0.02)

    assert campo.escrituras() == [arqueo_tasks.BORRAR_CAMPO_FECHA, '03072026']


# ---------------------------------------------------------------------------
# El orden, que es el arreglo de verdad
# ---------------------------------------------------------------------------

def _rango_nunca_invertido(desde_previo, hasta_previo, fecha):
    """Reproduce la secuencia de escrituras y devuelve los pasos en los que
    `desde > hasta`, que es lo que hace saltar el modal de SICAL."""
    desde, hasta = desde_previo, hasta_previo
    invertidos = []

    def paso(nombre):
        if desde and hasta and desde > hasta:
            invertidos.append(nombre)

    hasta = arqueo_tasks.FECHA_TOPE_SUPERIOR[4:8] + arqueo_tasks.FECHA_TOPE_SUPERIOR[2:4] + arqueo_tasks.FECHA_TOPE_SUPERIOR[0:2]
    paso('1: tope provisional')
    desde = fecha[4:8] + fecha[2:4] + fecha[0:2]
    paso('2: fecha desde')
    hasta = fecha[4:8] + fecha[2:4] + fecha[0:2]
    paso('3: fecha hasta')
    return invertidos


@pytest.mark.unit
@pytest.mark.parametrize('previa, nueva, caso', [
    ('05062026', '01072026', 'fecha nueva POSTERIOR (los 8 fallos del 31/08)'),
    ('14082026', '05062026', 'fecha nueva ANTERIOR (el caso simetrico)'),
    ('03072026', '03072026', 'misma fecha'),
])
def test_la_secuencia_nunca_deja_desde_mayor_que_hasta(previa, nueva, caso):
    iso = lambda d: d[4:8] + d[2:4] + d[0:2]
    invertidos = _rango_nunca_invertido(iso(previa), iso(previa), nueva)
    assert invertidos == [], f'{caso}: rango invertido en {invertidos}'


@pytest.mark.unit
def test_se_ensancha_el_tope_antes_de_escribir_la_fecha():
    """Esta es la regresion.

    Se lee del fuente real en vez de copiarlo, para que la prueba no pueda
    quedarse con una version vieja del codigo (mismo criterio que
    tests/test-fin-grupo.js en sical-robot).
    """
    fuente = inspect.getsource(arqueo_tasks._check_for_duplicates)

    llamadas = re.findall(
        r"_escribir_fecha\(\s*(\w+),\s*([\w'. ]+?),", fuente)

    assert len(llamadas) == 3, f'se esperaban 3 escrituras, hay {llamadas}'

    (campo1, val1), (campo2, _), (campo3, _) = llamadas

    assert val1.strip() == 'FECHA_TOPE_SUPERIOR', (
        'la primera escritura debe ensanchar el tope superior, no poner la '
        f'fecha real; se encontro {val1!r}')
    assert campo1 == 'to_date_field', 'el tope va en `hasta`'
    assert campo2 == 'from_date_field', 'despues el `desde`'
    assert campo3 == 'to_date_field', 'y al final se estrecha el `hasta`'


@pytest.mark.unit
def test_no_reaparecen_las_dos_formas_de_escribir_que_no_funcionan():
    """Las dos se probaron y las dos fallan en este control:

    - `{Ctrl}a`: un TMaskEdit de Delphi no lo procesa, asi que el campo se
      quedaria con la fecha anterior y volveria el fallo del 31/08/2026.
    - `{Home}` + digitos: se come el `0` inicial del mes (01/09/2026).
    - `double_click()`: selecciona solo una parte del campo, asi que los
      digitos entran por un punto medio.
    """
    fuente = inspect.getsource(arqueo_tasks._escribir_fecha)
    # Solo el codigo: los comentarios SI las nombran, para explicar por que no
    # se usan.
    codigo = '\n'.join(l for l in fuente.splitlines()
                       if not l.lstrip().startswith('#'))

    assert '{Ctrl}a' not in codigo
    assert '{Home}' not in codigo
    assert 'double_click' not in codigo


# ---------------------------------------------------------------------------
# Ciclo de vida de las ventanas: lo que hace gastos_robot
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_se_reutiliza_la_ventana_de_consulta():
    """Reutilizar la ConOpera que hubiera abierta es la causa raiz: la tarea
    heredaba los campos de la anterior, y a veces un modal encima. gastos_robot
    la abre siempre desde el menu y por eso no le pasa."""
    fuente = inspect.getsource(arqueo_tasks._check_for_duplicates)

    assert 'already open, reusing' not in fuente
    assert '_dejar_sical_sin_ventanas_de_consulta()' in fuente
    assert 'abrir_ventana_opcion_en_menu' in fuente


@pytest.mark.unit
def test_las_ventanas_se_cierran_tambien_cuando_falla():
    """Sin `finally`, un fallo deja el modal y FilOpera abiertos y envenena a
    la tarea siguiente: la cadena no se corta sola."""
    fuente = inspect.getsource(arqueo_tasks._check_for_duplicates)

    assert 'finally:' in fuente
    # Una al entrar (estado conocido) y otra al salir (pase lo que pase).
    assert fuente.count('_dejar_sical_sin_ventanas_de_consulta()') >= 2

    # Y los cierres a mano de cada rama desaparecen, o los dos caminos
    # volverian a poder divergir.
    assert "CONSULTA_FORM_PATHS['salir_button']" not in fuente
    assert "FILTROS_FORM_PATHS['cerrar_button']" not in fuente


@pytest.mark.unit
def test_cerrar_una_ventana_comprueba_que_se_fue():
    """`name:"Cerrar"` es ambiguo -- con un modal encima hay dos, y el primero
    en orden de arbol es el del modal. Clicar y dar por cerrada la ventana es
    justo como se quedaba abierta."""
    fuente = inspect.getsource(arqueo_tasks._cerrar_ventana_sical)

    assert '_esperar_cierre' in fuente
    assert '_ventana_abierta' in inspect.getsource(arqueo_tasks._esperar_cierre)
    assert 'TBitBtn' in fuente, 'debe intentar primero el boton real de la ventana'
