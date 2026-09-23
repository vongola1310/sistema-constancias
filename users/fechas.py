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
    """Lee Día | Mes | Año y sus valores en la fila siguiente.

    Devuelve None si no encuentra este formato.
    """
    for i, fila in enumerate(filas[:12]):
        columnas = {
            _normalizar(valor): j
            for j, valor in enumerate(fila)
            if valor is not None
        }

        dia_col = columnas.get('dia', columnas.get('dias'))
        if dia_col is None or 'mes' not in columnas or 'ano' not in columnas:
            continue

        valores = filas[i + 1] if i + 1 < len(filas) else []

        def celda(col):
            return valores[col] if col < len(valores) else None

        dias_raw = celda(dia_col)
        mes_raw = celda(columnas['mes'])
        anio_raw = celda(columnas['ano'])

        if isinstance(dias_raw, float) and dias_raw.is_integer():
            dias_raw = int(dias_raw)

        texto_dias = str(dias_raw or '').strip().lower()

        if not re.fullmatch(
            r'\d{1,2}(?:\s*(?:,|;|y)\s*\d{1,2})*',
            texto_dias
        ):
            raise ValueError(
                'Escribe los días como 8, 9, 10 o 8 y 10.'
            )

        meses = {
            nombre: n
            for n, nombre in enumerate(MESES)
            if nombre
        }
        meses.update({
            nombre[:3]: n
            for n, nombre in enumerate(MESES)
            if nombre
        })
        meses.update({'setiembre': 9, 'set': 9})

        mes_texto = _normalizar(mes_raw).rstrip('.')
        mes = meses.get(mes_texto)

        if mes is None and re.fullmatch(
            r'\d{1,2}(?:\.0)?', mes_texto
        ):
            mes = int(float(mes_texto))

        anio_texto = str(anio_raw or '').strip()

        if mes is None or not re.fullmatch(
            r'\d{4}(?:\.0)?', anio_texto
        ):
            raise ValueError(
                'Revisa el mes y el año de cuatro dígitos en el Excel.'
            )

        try:
            anio = int(float(anio_texto))
            return sorted({
                date(anio, mes, int(d))
                for d in re.findall(r'\d+', texto_dias)
            })
        except ValueError as exc:
            raise ValueError(
                'La capacitación contiene una fecha inexistente.'
            ) from exc

    return None


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