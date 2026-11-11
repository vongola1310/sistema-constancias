"""Resumen y descarga del conjunto exacto procesado en el paso 2 del libro."""
import logging
import tempfile
import uuid
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Constancia

logger = logging.getLogger(__name__)
RESULTADOS_SESSION_KEY = 'libro_resultados'
MAX_RESULTADOS = 5


def guardar_resultado_libro(request, ids, sesiones, creadas, actualizadas):
    lote_id = str(uuid.uuid4())
    resultados = request.session.get(RESULTADOS_SESSION_KEY, {})
    resultados[lote_id] = {
        'usuario_id': request.user.pk,
        'constancia_ids': sorted(ids),
        'sesiones': sesiones,
        'total': len(ids),
        'nuevas': len(creadas),
        'actualizadas': len(actualizadas - creadas),
        'existentes': len(ids - creadas - actualizadas),
    }
    # Las pestañas de generaciones recientes mantienen su propia selección.
    request.session[RESULTADOS_SESSION_KEY] = dict(list(resultados.items())[-MAX_RESULTADOS:])
    return lote_id


def _resultado(request, lote_id):
    resultado = request.session.get(RESULTADOS_SESSION_KEY, {}).get(str(lote_id))
    if resultado and resultado.get('usuario_id') == request.user.pk:
        return resultado
    return None


def _pantalla_resultado(request, lote_id, resultado, error='', status=200):
    return render(request, 'users/libro_resultado.html', {
        'lote_id': lote_id, 'resultado': resultado, 'error_descarga': error,
    }, status=status)


@never_cache
@login_required
@require_GET
def libro_resultado_view(request, lote_id):
    resultado = _resultado(request, lote_id)
    return _pantalla_resultado(request, lote_id, resultado, status=200 if resultado else 404)


@never_cache
@login_required
@require_GET
def descargar_libro_resultado_view(request, lote_id):
    resultado = _resultado(request, lote_id)
    if not resultado:
        return _pantalla_resultado(request, lote_id, None, status=404)

    # Los IDs proceden de la generación guardada en la sesión, nunca del navegador.
    ids = resultado['constancia_ids']
    constancias = list(Constancia.objects.filter(pk__in=ids).select_related(
        'participante', 'curso', 'firma_gerente', 'firma_especialista',
    ).order_by('fecha_inicio', 'curso_id', 'participante__nombre_completo', 'pk'))
    if not ids or len(constancias) != len(ids):
        return _pantalla_resultado(
            request, lote_id, resultado,
            'Alguna constancia de esta selección ya no está disponible. Revisa el historial o vuelve a procesar las sesiones para actualizar la descarga.',
            status=410,
        )

    # Importación local: el generador PDF existente reside en el módulo de vistas.
    from .views import _generar_pdf_bytes

    archivo = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with zipfile.ZipFile(archivo, 'w', zipfile.ZIP_DEFLATED) as paquete:
            for constancia in constancias:
                curso = slugify(constancia.curso.nombre)[:70] or 'curso'
                participante = slugify(constancia.participante.nombre_completo)[:80] or 'participante'
                carpeta = f'{constancia.fecha_inicio.isoformat()}_{curso}_{constancia.curso_id}'
                nombre = f'{carpeta}/constancia_{participante}_{constancia.pk}.pdf'
                pdf = _generar_pdf_bytes(constancia)
                if not pdf:
                    raise ValueError('El generador no devolvió el PDF de una constancia.')
                paquete.writestr(nombre, pdf)
        archivo.seek(0)
        return FileResponse(
            archivo, as_attachment=True, content_type='application/zip',
            filename=f'constancias-fechas-seleccionadas-{str(lote_id)[:8]}.zip',
        )
    except Exception:
        archivo.close()
        logger.exception('Error preparando el ZIP del libro, lote %s', lote_id)
        return _pantalla_resultado(
            request, lote_id, resultado,
            'No se pudo preparar la descarga. Las constancias siguen guardadas; vuelve a intentar con el botón de descarga.',
            status=500,
        )
