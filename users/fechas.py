import re
import unicodedata
from datetime import date

MESES = (
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
)


def _normalizar(valor):
    texto = unicodedata.normalize('NFD', str(valor or '').lower())
    return ''.join(
        c for c in texto if unicodedata.category(c) != 'Mn'
    ).strip().rstrip(':')


def leer_fechas_excel(filas):
    """Lee el bloque Día | Mes | Año, con uno o varios días por fila.

    Las filas consecutivas pueden compartir mes y año (celdas combinadas).
    Devuelve None si no encuentra este formato. Las filas recibidas deben
    corresponder a los metadatos, antes del encabezado de participantes.
    """
    for i, fila in enumerate(filas):
        columnas = {
            _normalizar(valor): j
            for j, valor in enumerate(fila)
            if valor is not None
        }

        dia_col = columnas.get('dia', columnas.get('dias'))
        if dia_col is None or 'mes' not in columnas or 'ano' not in columnas:
            continue

        fechas = set()
        mes_anterior = None
        anio_anterior = None
        for valores in filas[i + 1:]:
            def celda(col):
                return valores[col] if col < len(valores) else None

            dias_raw = celda(dia_col)
            mes_raw = celda(columnas['mes'])
            anio_raw = celda(columnas['ano'])
            if all(v is None or str(v).strip() == '' for v in (dias_raw, mes_raw, anio_raw)):
                break
            if mes_raw is None or str(mes_raw).strip() == '':
                mes_raw = mes_anterior
            if anio_raw is None or str(anio_raw).strip() == '':
                anio_raw = anio_anterior
            fechas.update(_leer_dias_mes_anio(dias_raw, mes_raw, anio_raw))
            mes_anterior, anio_anterior = mes_raw, anio_raw

        if not fechas:
            raise ValueError('Escribe las fechas debajo de Día, Mes y Año.')
        return sorted(fechas)

    return None


def _leer_dias_mes_anio(dias_raw, mes_raw, anio_raw):
    if isinstance(dias_raw, float) and dias_raw.is_integer():
        dias_raw = int(dias_raw)

    texto_dias = str(dias_raw or '').strip().lower()

    if not re.fullmatch(r'\d{1,2}(?:\s*(?:,|;|y)\s*\d{1,2})*', texto_dias):
        raise ValueError('Escribe los días como 8, 9, 10 o 8 y 10.')

    meses = {nombre: n for n, nombre in enumerate(MESES) if nombre}
    meses.update({nombre[:3]: n for n, nombre in enumerate(MESES) if nombre})
    meses.update({'setiembre': 9, 'set': 9})

    mes_texto = _normalizar(mes_raw).rstrip('.')
    mes = meses.get(mes_texto)
    if mes is None and re.fullmatch(r'\d{1,2}(?:\.0)?', mes_texto):
        mes = int(float(mes_texto))

    anio_texto = str(anio_raw or '').strip()
    if mes is None or not re.fullmatch(r'\d{4}(?:\.0)?', anio_texto):
        raise ValueError('Revisa el mes y el año de cuatro dígitos en el Excel.')

    try:
        anio = int(float(anio_texto))
        return {date(anio, mes, int(d)) for d in re.findall(r'\d+', texto_dias)}
    except ValueError as exc:
        raise ValueError('La capacitación contiene una fecha inexistente.') from exc


def leer_fechas_texto(texto, anio=None):
    """Lee, por ejemplo, '13,14 y 15 de septiembre del 2026'."""
    texto = _normalizar(texto)
    patron = (
        r'(?<![\d,])'
        r'(?P<dias>\d{1,2}(?:(?:\s*(?:,|;|\by\b)\s*|\s+)\d{1,2})*)'
        r'\s+de\s+(?P<mes>[a-z]+)'
        r'(?:\s+(?:del?\s+)?(?P<anio>\d{4})\b)?'
    )
    coincidencia = re.search(patron, texto)
    if not coincidencia:
        return None
    dias = ', '.join(re.findall(r'\d+', coincidencia['dias']))
    return sorted(_leer_dias_mes_anio(
        dias, coincidencia['mes'], coincidencia['anio'] or anio or date.today().year
    ))


def formatear_fechas(fechas):
    """Enumera las fechas guardadas, sin agregar días intermedios."""
    fechas = sorted({
        date.fromisoformat(f) if isinstance(f, str) else f
        for f in fechas
    })

    if not fechas:
        return ''

    def unir(partes):
        if len(partes) == 1:
            return partes[0]
        return ', '.join(partes[:-1]) + ' y ' + partes[-1]

    primera = fechas[0]

    if all(
        (f.year, f.month) == (primera.year, primera.month)
        for f in fechas
    ):
        dias = unir([str(f.day) for f in fechas])
        return (
            f'{dias} de {MESES[primera.month]} de {primera.year}'
        )

    return unir([
        f'{f.day} de {MESES[f.month]} de {f.year}'
        for f in fechas
    ])
