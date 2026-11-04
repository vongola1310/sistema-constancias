from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Evaluador


def requiere_acceso(atributo, mensaje):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not getattr(request.user, atributo, False):
                return render(request, 'users/acceso_denegado.html', {
                    'motivo': mensaje,
                }, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


administrador_required = requiere_acceso(
    'administra_accesos', 'Solo los administradores pueden gestionar usuarios y sus accesos.',
)
creacion_constancias_required = requiere_acceso(
    'tiene_acceso_constancias',
    'Tu cuenta no tiene permiso para crear constancias. Solicita acceso a un administrador.',
)


def filtros_accesos(datos):
    busqueda = datos.get('acceso_q', '').strip()[:150]
    estado = datos.get('acceso_estado', '')
    if estado not in ('autorizados', 'sin_permiso', 'inactivos'):
        estado = ''
    pagina = datos.get('acceso_pagina', '1')
    if not pagina.isascii() or not pagina.isdecimal() or len(pagina) > 8:
        pagina = '1'
    return {'acceso_q': busqueda, 'acceso_estado': estado, 'acceso_pagina': pagina}


def contexto_accesos(request):
    if not request.user.administra_accesos:
        return {}
    filtros = filtros_accesos(request.GET)
    usuarios = Evaluador.objects.only(
        'id', 'username', 'first_name', 'last_name', 'email', 'cargo',
        'is_active', 'is_superuser', 'puede_crear_constancias',
    ).order_by('first_name', 'last_name', 'username', 'pk')
    autorizados = Q(is_active=True) & (Q(is_superuser=True) | Q(puede_crear_constancias=True))
    resumen = usuarios.aggregate(
        total=Count('pk'), autorizados=Count('pk', filter=autorizados),
        sin_permiso=Count('pk', filter=Q(is_active=True, is_superuser=False, puede_crear_constancias=False)),
        inactivos=Count('pk', filter=Q(is_active=False)),
    )
    if filtros['acceso_q']:
        # Cada palabra puede coincidir con nombre, apellido, usuario o correo.
        for palabra in filtros['acceso_q'].split():
            usuarios = usuarios.filter(
                Q(username__icontains=palabra) | Q(first_name__icontains=palabra)
                | Q(last_name__icontains=palabra) | Q(email__icontains=palabra)
            )
    if filtros['acceso_estado'] == 'autorizados':
        usuarios = usuarios.filter(autorizados)
    elif filtros['acceso_estado'] == 'sin_permiso':
        usuarios = usuarios.filter(is_active=True, is_superuser=False, puede_crear_constancias=False)
    elif filtros['acceso_estado'] == 'inactivos':
        usuarios = usuarios.filter(is_active=False)
    pagina = Paginator(usuarios, 10).get_page(filtros['acceso_pagina'])
    filtros['acceso_pagina'] = str(pagina.number)
    return {
        'accesos_resumen': resumen, 'accesos_pagina': pagina, **filtros,
        'accesos_query': urlencode({k: v for k, v in filtros.items() if k != 'acceso_pagina'}),
    }


class AccesoUsuarioForm(forms.Form):
    is_active = forms.BooleanField(required=False)
    puede_crear_constancias = forms.BooleanField(required=False)
    estado_anterior = forms.ChoiceField(choices=[(v, v) for v in ('0:0', '0:1', '1:0', '1:1')])


@administrador_required
@require_POST
def actualizar_acceso_view(request, pk):
    form = AccesoUsuarioForm(request.POST)
    destino = reverse('users:dashboard') + '?' + urlencode(filtros_accesos(request.POST)) + '#accesos'
    with transaction.atomic():
        usuario = get_object_or_404(Evaluador.objects.select_for_update(), pk=pk)
        # Las cuentas administradoras se conservan para evitar bloqueos y escalamiento.
        if usuario.is_superuser or usuario.pk == request.user.pk:
            return render(request, 'users/acceso_denegado.html', {
                'motivo': 'Las cuentas administradoras están protegidas y no se modifican desde este panel.',
            }, status=403)
        if not form.is_valid():
            messages.error(request, 'No se guardó el acceso. Recarga el panel e intenta nuevamente.')
        elif form.cleaned_data['estado_anterior'] != f'{int(usuario.is_active)}:{int(usuario.puede_crear_constancias)}':
            messages.error(request, 'Otro administrador modificó este acceso. Revisa su estado actual antes de guardar.')
        else:
            usuario.is_active = form.cleaned_data['is_active']
            usuario.puede_crear_constancias = form.cleaned_data['puede_crear_constancias']
            usuario.save(update_fields=['is_active', 'puede_crear_constancias'])
            estado = ('cuenta desactivada' if not usuario.is_active else
                      'creación de constancias habilitada' if usuario.puede_crear_constancias else
                      'creación de constancias sin permiso')
            messages.success(request, f'Acceso actualizado para {usuario}: {estado}.')
    return redirect(destino)
