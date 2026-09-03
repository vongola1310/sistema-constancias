import os
import uuid
import io
import base64
import mimetypes
import zipfile
import openpyxl
import csv
from io import BytesIO
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.contrib.staticfiles import finders
from django.conf import settings
import os
from datetime import date, timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
import os
from . import importadores
from django.conf import settings
from .models import Participante, Curso, Constancia
from django.http import HttpResponse, JsonResponse
from .forms import (
    EvaluadorCreationForm, ProfilePhotoForm, SignatureForm, 
    CursoForm, ParticipanteForm, InstitucionForm, LoteConstanciaForm,
    WebinarStep1Form, EncuestaForm, LibroCapacitacionesForm
)
from . import importadores
from .models import (
    Constancia, Evaluador, Curso, Participante, Institucion,
    EncuestaRespuesta, LeadVenta
)
from django.db.models import Q
# --- VISTAS DE AUTENTICACIÓN Y PERFIL ---

def login_view(request):
    error = None
    if request.method == 'POST':
        username_from_form = request.POST.get('username')
        password_from_form = request.POST.get('password')
        user = authenticate(request, username=username_from_form, password=password_from_form)
        if user is not None:
            login(request, user)
            return redirect('users:dashboard')
        else:
            error = "El usuario o la contraseña son incorrectos. Por favor, inténtalo de nuevo."
    context = {'error': error}
    return render(request, 'users/login.html', context)

@login_required
def dashboard_view(request):
    hoy = timezone.now().date()
    
    constancias_vencidas = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__lt=hoy
    )
    
    limite_30_dias = hoy + timedelta(days=30)
    constancias_por_vencer = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_30_dias
    )

    context = {
        'user': request.user,
        'constancias_vencidas': constancias_vencidas,
        'constancias_por_vencer': constancias_por_vencer,
    }
    return render(request, 'users/dashboard.html', context)

@login_required
def change_photo_view(request):
    if request.method == 'POST':
        form = ProfilePhotoForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('users:dashboard')
    else:
        form = ProfilePhotoForm(instance=request.user)
    return render(request, 'users/change_photo.html', {'form': form})

@login_required
def change_signature_view(request):
    if request.method == 'POST':
        form = SignatureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('users:dashboard')
    else:
        form = SignatureForm(instance=request.user)
    return render(request, 'users/change_signature.html', {'form': form})

# --- VISTAS DE CREACIÓN Y GESTIÓN DE OBJETOS ---
@login_required
def crear_evaluador_view(request):
    if request.method == 'POST':
        form = EvaluadorCreationForm(request.POST, request.FILES)
        if form.is_valid():
            new_user = form.save()
            login(request, new_user)
            return redirect('users:dashboard')
    else:
        form = EvaluadorCreationForm()
    context = {'form': form}
    return render(request, 'users/crear_evaluador.html', context)

@login_required
def crear_curso_view(request):
    if request.method == 'POST':
        form = CursoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡La definición del curso ha sido creada exitosamente!')
            return redirect('users:dashboard')
    else:
        form = CursoForm()
    context = {'form': form}
    return render(request, 'users/crear_curso.html', context)

@login_required
def lista_participantes_view(request):
    participantes = Participante.objects.all().order_by('nombre_completo')
    context = {
        'participantes': participantes
    }
    return render(request, 'users/lista_participantes.html', context)

@login_required
def crear_participante_view(request):
    if request.method == 'POST':
        form = ParticipanteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡El participante ha sido registrado exitosamente!')
            return redirect('users:lista_participantes')
    else:
        form = ParticipanteForm()
    context = {'form': form}
    return render(request, 'users/crear_participante.html', context)

@login_required
def editar_participante_view(request, pk):
    participante = get_object_or_404(Participante, pk=pk)
    if request.method == 'POST':
        form = ParticipanteForm(request.POST, instance=participante)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Los datos del participante han sido actualizados!')
            return redirect('users:lista_participantes')
    else:
        form = ParticipanteForm(instance=participante)
    context = {'form': form, 'participante': participante}
    return render(request, 'users/editar_participante.html', context)

@login_required
def crear_institucion_view(request):
    if request.method == 'POST':
        form = InstitucionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡La institución ha sido registrada!')
            return redirect('users:crear_participante')
    else:
        form = InstitucionForm()
    context = {'form': form}
    return render(request, 'users/crear_institucion.html', context)

# --- VISTAS DE CONSTANCIAS ---

@login_required
def crear_lote_constancias_view(request):
    if request.method == 'POST':
        form = LoteConstanciaForm(request.POST)
        if form.is_valid():
            curso = form.cleaned_data['curso']
            participantes_seleccionados = form.cleaned_data['participantes']
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_termino = form.cleaned_data['fecha_termino']
            duracion = form.cleaned_data['duracion_en_horas']
            especialista = form.cleaned_data['firma_especialista']
            try:
                gerente = Evaluador.objects.get(es_gerente=True)
            except Evaluador.DoesNotExist:
                messages.error(request, 'Error: No se ha designado un gerente en el sistema.')
                return redirect('users:dashboard')
            constancias_creadas = 0
            for participante in participantes_seleccionados:
                constancia, created = Constancia.objects.get_or_create(
                    participante=participante,
                    curso=curso,
                    fecha_inicio=fecha_inicio,
                    defaults={
                        'fecha_termino': fecha_termino,
                        'duracion_en_horas': duracion,
                        'firma_gerente': gerente,
                        'firma_especialista': especialista,
                        'codigo_verificacion': str(uuid.uuid4()).split('-')[0].upper(),
                        'es_webinar': False,
                        'tipo': 'curso'
                        
                    }
                )
                if created:
                    constancia.fecha_vencimiento = constancia.fecha_emision + relativedelta(years=1)
                    constancia.save()
                    constancias_creadas += 1
            messages.success(request, f'¡Se crearon {constancias_creadas} constancias de curso exitosamente!')
            return redirect('users:historial_constancias')
    else:
        form = LoteConstanciaForm()
    context = {'form': form}
    return render(request, 'users/crear_lote_constancias.html', context)
    
@login_required
def historial_constancias_view(request):
    filtro_tipo = request.GET.get('tipo', None)
    busqueda = request.GET.get('q', '').strip()

    lista_constancias = Constancia.objects.all()

    if filtro_tipo == 'webinar':
        lista_constancias = lista_constancias.filter(es_webinar=True)
    elif filtro_tipo == 'curso':
        lista_constancias = lista_constancias.filter(es_webinar=False)

    if busqueda:
        lista_constancias = lista_constancias.filter(
            Q(participante__nombre_completo__icontains=busqueda) |
            Q(participante__email__icontains=busqueda)
        )

    constancias_ordenadas = lista_constancias.order_by('-fecha_emision')
    paginator = Paginator(constancias_ordenadas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'filtro_activo': filtro_tipo,
        'busqueda': busqueda,
    }
    return render(request, 'users/historial_constancias.html', context)
    # Obtenemos el parámetro 'tipo' de la URL. Si no existe, es None.
    filtro_tipo = request.GET.get('tipo', None)
    
    # Empezamos con todas las constancias
    lista_constancias = Constancia.objects.all()
    
    # Aplicamos el filtro solo si se especifica uno
    if filtro_tipo == 'webinar':
        lista_constancias = lista_constancias.filter(es_webinar=True)
    elif filtro_tipo == 'curso':
        lista_constancias = lista_constancias.filter(es_webinar=False)
    
    # Ordenamos y paginamos el resultado
    constancias_ordenadas = lista_constancias.order_by('-fecha_emision')
    paginator = Paginator(constancias_ordenadas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filtro_activo': filtro_tipo
    }
    return render(request, 'users/historial_constancias.html', context)


@login_required
def borrar_constancias_view(request):
    if request.method == 'POST':
        ids_a_borrar = request.POST.getlist('constancia_ids')
        if ids_a_borrar:
            Constancia.objects.filter(pk__in=ids_a_borrar).delete()
            messages.success(request, f"Se eliminaron {len(ids_a_borrar)} constancias exitosamente.")
        else:
            messages.warning(request, "No se seleccionó ninguna constancia para eliminar.")
    return redirect('users:historial_constancias')

@login_required
def descargar_constancias_zip_view(request):
    if request.method == 'POST':
        ids_a_descargar = request.POST.getlist('constancia_ids')
        if not ids_a_descargar:
            messages.warning(request, "No se seleccionó ninguna constancia para descargar.")
            return redirect('users:historial_constancias')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for constancia_id in ids_a_descargar:
                constancia = get_object_or_404(Constancia, pk=constancia_id)
                pdf_bytes = _generar_pdf_bytes(constancia)
                filename = f"constancia_{constancia.participante.nombre_completo}_{constancia.pk}.pdf"
                zip_file.writestr(filename, pdf_bytes)
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="constancias.zip"'
        return response
    return redirect('users:historial_constancias')

@login_required
def historial_participante_view(request, pk):
    participante = get_object_or_404(Participante, pk=pk)
    constancias = participante.constancia_set.all().order_by('-fecha_emision')
    context = {
        'participante': participante,
        'constancias': constancias,
    }
    return render(request, 'users/historial_participante.html', context)

# --- VISTAS DEL ASISTENTE DE WEBINAR ---
import csv
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
MINUTOS_MINIMOS = 30  # Umbral para que un asistente califique
 
 
@login_required
def webinar_paso1_subir_view(request):
    if request.method == 'POST':
        form = WebinarStep1Form(request.POST, request.FILES)
        if form.is_valid():
            request.session['webinar_event_data'] = {
                'curso_nombre': form.cleaned_data['curso_nombre'],
                'fecha_inicio': form.cleaned_data['fecha_inicio'].isoformat(),
                'fecha_termino': form.cleaned_data['fecha_termino'].isoformat(),
                'duracion_en_horas': float(form.cleaned_data['duracion_en_horas']),
                'firma_especialista_id': form.cleaned_data['firma_especialista'].id,
            }
 
            archivo = form.cleaned_data['archivo_csv']
 
            # 1) Leer el reporte de asistencia (Teams, WebEx, Zoom o Excel)
            try:
                asistentes, formato = importadores.parsear_asistencia(
                    archivo.read(), archivo.name
                )
            except ValueError as e:
                messages.error(request, f"No se pudo leer el archivo: {e}")
                return redirect('users:webinar_paso1')
            except Exception:
                messages.error(
                    request,
                    "El archivo no pudo procesarse. Verifica que sea el reporte "
                    "de asistencia y no esté dañado."
                )
                return redirect('users:webinar_paso1')
 
            if not asistentes:
                messages.error(request, "El archivo no contiene participantes.")
                return redirect('users:webinar_paso1')
 
            # 2) Completar correos faltantes con el padrón (opcional)
            padron = []
            archivo_padron = form.cleaned_data.get('archivo_padron')
            if archivo_padron:
                try:
                    padron = importadores.cargar_padron(archivo_padron.read())
                except Exception:
                    messages.warning(
                        request,
                        "No se pudo leer el Excel de inscritos; se continuó sin él."
                    )
 
            asistentes, pendientes = importadores.completar_correos(asistentes, padron)
 
            # 3) Clasificar
            calificados, no_calificados, sin_correo = [], [], []
            for a in asistentes:
                info = {
                    'nombre_completo': a['nombre_completo'],
                    'email': a['email'],
                    'institucion': a['institucion'],
                    'duracion_total': a['duracion_total'],
                    'estado_correo': a.get('estado_correo', 'original'),
                }
                if not a['email']:
                    if a['duracion_total'] >= MINUTOS_MINIMOS:
                        info['sugerencias'] = a.get('sugerencias', [])
                        sin_correo.append(info)
                elif a['duracion_total'] >= MINUTOS_MINIMOS:
                    calificados.append(info)
                else:
                    no_calificados.append(info)
 
            calificados.sort(key=lambda x: -x['duracion_total'])
            no_calificados.sort(key=lambda x: -x['duracion_total'])
            sin_correo.sort(key=lambda x: -x['duracion_total'])
 
            request.session['webinar_participantes_calificados'] = calificados
            request.session['webinar_participantes_no_calificados'] = no_calificados
            request.session['webinar_pendientes'] = sin_correo
 
            recuperados = sum(1 for p in calificados if p['estado_correo'] == 'recuperado')
            if recuperados:
                messages.success(
                    request,
                    f"Se recuperaron {recuperados} correo(s) desde el Excel de inscritos."
                )
            if sin_correo:
                messages.warning(
                    request,
                    f"{len(sin_correo)} asistente(s) califican pero no tienen correo. "
                    "Complétalos abajo o quedarán fuera."
                )
 
            return redirect('users:webinar_paso2')
    else:
        form = WebinarStep1Form()
 
    return render(request, 'users/webinar_paso1_subir.html', {'form': form})
 
 
@login_required
def webinar_paso2_previsualizar_view(request):
    event_data = request.session.get('webinar_event_data')
    participantes = request.session.get('webinar_participantes_calificados')
    no_calificados = request.session.get('webinar_participantes_no_calificados')
    pendientes = request.session.get('webinar_pendientes', [])
 
    if not event_data or participantes is None:
        messages.error(request, "No hay datos para procesar.")
        return redirect('users:webinar_paso1')
 
    if request.method == 'POST':
        # --- Incorporar los correos capturados a mano ---
        agregados = 0
        for i, p in enumerate(pendientes):
            correo = request.POST.get(f'correo_pendiente_{i}', '').strip().lower()
            if not correo:
                continue
            if not importadores._es_correo(correo):
                messages.error(
                    request,
                    f"El correo de {p['nombre_completo']} no es válido: {correo}"
                )
                return redirect('users:webinar_paso2')
            if any(x['email'] == correo for x in participantes):
                continue
            participantes.append({
                'nombre_completo': p['nombre_completo'],
                'email': correo,
                'institucion': p['institucion'],
                'duracion_total': p['duracion_total'],
                'estado_correo': 'manual',
            })
            agregados += 1
 
        if not participantes:
            messages.error(request, "No hay participantes con correo para generar constancias.")
            return redirect('users:webinar_paso2')
 
        try:
            with transaction.atomic():
                curso = Curso.objects.create(nombre=event_data['curso_nombre'])
 
                firma_e_id = event_data.get('firma_especialista_id')
                firma_especialista = (
                    Evaluador.objects.filter(id=firma_e_id).first() if firma_e_id else None
                )
                firma_gerente = Evaluador.objects.filter(es_gerente=True).first()
 
                for p_data in participantes:
                    participante, created = Participante.objects.get_or_create(
                        email=p_data['email'],
                        defaults={
                            'nombre_completo': p_data['nombre_completo'],
                            'institucion_id': None,
                        }
                    )
                    if not created:
                        participante.nombre_completo = p_data['nombre_completo']
                        participante.save()
 
                    nuevo_codigo = str(uuid.uuid4()).split('-')[0].upper()
 
                    Constancia.objects.create(
                        participante=participante,
                        curso=curso,
                        fecha_inicio=event_data['fecha_inicio'],
                        fecha_termino=event_data['fecha_termino'],
                        duracion_en_horas=event_data['duracion_en_horas'],
                        firma_gerente=firma_gerente,
                        firma_especialista=firma_especialista,
                        codigo_verificacion=nuevo_codigo,
                        es_webinar=True,
                         tipo='webinar'
                    )
 
            for clave in ('webinar_event_data', 'webinar_participantes_calificados',
                          'webinar_participantes_no_calificados', 'webinar_pendientes'):
                request.session.pop(clave, None)
 
            extra = f" (incluidos {agregados} capturados a mano)" if agregados else ""
            messages.success(
                request,
                f"¡Éxito! Se generaron {len(participantes)} constancias correctamente{extra}."
            )
            return redirect('users:historial_constancias')
 
        except Exception as e:
            messages.error(request, f"Hubo un error al generar las constancias: {str(e)}")
            return redirect('users:webinar_paso2')
 
    context = {
        'participantes': participantes,
        'no_calificados': no_calificados,
        'pendientes': pendientes,
        'evento': event_data,
    }
    return render(request, 'users/webinar_paso2_previsualizar.html', context)

    

from django.db import transaction
from .models import Participante, Curso, Constancia
from .models import Participante, Curso, Constancia, Evaluador


# --- VISTA DE LA ENCUESTA ---

def encuesta_view(request, token):
    constancia = get_object_or_404(Constancia, token_encuesta=token)
    if EncuestaRespuesta.objects.filter(constancia=constancia).exists():
        return render(request, 'users/encuesta_gracias.html', {'mensaje': 'Ya has completado esta encuesta anteriormente. ¡Gracias!'})
    if request.method == 'POST':
        form = EncuestaForm(request.POST)
        if form.is_valid():
            respuesta = form.save(commit=False)
            respuesta.constancia = constancia
            respuesta.nombre_completo = constancia.participante.nombre_completo
            respuesta.email = constancia.participante.email
            respuesta.save()
            if form.cleaned_data.get('interes_productos'):
                LeadVenta.objects.get_or_create(
                    participante=constancia.participante,
                    curso=constancia.curso
                )
            return render(request, 'users/encuesta_gracias.html', {'mensaje': '¡Gracias por tus respuestas! Tu constancia está siendo procesada.'})
    else:
        form = EncuestaForm()
    context = {'form': form, 'constancia': constancia}
    return render(request, 'users/encuesta.html', context)

# --- LÓGICA DE GENERACIÓN DE PDF ---
import os
import tempfile
import requests
from django.conf import settings
from PIL import Image  # <--- NUEVO IMPORT
import io
import requests
import base64
import os

def _imagen_a_base64(imagen_source):
    """
    Descarga/Lee imagen, elimina transparencia (para evitar cuadros negros)
    y retorna Base64.
    """
    if not imagen_source:
        return ""

    try:
        image_data = None
        
        # 1. OBTENER LOS DATOS DE LA IMAGEN (Sea URL o Archivo Local)
        ruta_o_url = str(imagen_source)
        if hasattr(imagen_source, 'url'):
            ruta_o_url = imagen_source.url

        if ruta_o_url.startswith('http'):
            response = requests.get(ruta_o_url)
            if response.status_code == 200:
                image_data = response.content
        else:
            # Lógica para archivo local
            path_local = ""
            if hasattr(imagen_source, 'path'):
                try: path_local = imagen_source.path
                except: pass
            if not path_local: path_local = ruta_o_url
            
            if os.path.exists(path_local):
                with open(path_local, "rb") as f:
                    image_data = f.read()

        if not image_data:
            return ""

        # 2. PROCESAMIENTO CON PILLOW (El secreto anti-cuadros negros)
        img = Image.open(io.BytesIO(image_data))
        
        # Si tiene transparencia (RGBA), la convertimos a fondo blanco
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Crear lienzo blanco del mismo tamaño
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Convertir a RGBA para asegurar compatibilidad de pegado
            img = img.convert("RGBA")
            # Pegar la imagen original usando su canal alfa como máscara
            background.paste(img, mask=img.split()[3]) # 3 es el canal Alpha
            img = background
        else:
            img = img.convert("RGB")

        # 3. GUARDAR EN BUFFER COMO JPEG (Más ligero y sin transparencia)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        encoded = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return f"data:image/jpeg;base64,{encoded}"

    except Exception as e:
        print(f"Error procesando imagen {imagen_source}: {e}")
        return ""

    

def link_callback(uri, rel):
    if uri.startswith('data:'):
        return uri
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri
    # Para cualquier archivo local
    path = uri.lstrip('/').lstrip('\\')
    full_path = os.path.join(settings.BASE_DIR, 'static', path)
    if os.path.exists(full_path):
        return full_path
    return uri

def _generar_pdf_bytes(constancia):
    
    # 1. Procesar FONDO (Archivo Estático Local)
    # Construimos la ruta absoluta usando BASE_DIR para que funcione en Windows/Linux
    bg_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'fondo_constancia.png')

    if not os.path.exists(bg_path):
        bg_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'images', 'fondo_constancia.png')
    
    bg_url = _imagen_a_base64(bg_path)

    # 2. Procesar FIRMAS (Pueden estar en Local o en Cloudinary)
    firma_g_url = ""
    if constancia.firma_gerente and constancia.firma_gerente.firma_digital:
        firma_g_url = _imagen_a_base64(constancia.firma_gerente.firma_digital)

    firma_e_url = ""
    if constancia.firma_especialista and constancia.firma_especialista.firma_digital:
        firma_e_url = _imagen_a_base64(constancia.firma_especialista.firma_digital)

    # 3. Formateo de Fechas
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    f = constancia.fecha_termino
    fecha_texto = f"{f.day} de {meses[f.month]} de {f.year}" if f else ""
    duracion_formateada = f"{int(constancia.duracion_en_horas):02d}" if constancia.duracion_en_horas else "00"

    # 4. Preparar Contexto para el HTML
    context = {
        'constancia': constancia,
        'bg_url': bg_url,         # <--- Base64 del fondo
        'firma_g_url': firma_g_url, # <--- Base64 de firma gerente
        'firma_e_url': firma_e_url, # <--- Base64 de firma especialista
        'fecha_texto': fecha_texto,
        'duracion_formateada': duracion_formateada,
    }
    
    print(f"DEBUG especialista: {constancia.firma_especialista}")
    print(f"DEBUG especialista full_name: {constancia.firma_especialista.get_full_name()}")
    print(f"DEBUG especialista first_name: {constancia.firma_especialista.first_name}")
    print(f"DEBUG especialista last_name: {constancia.firma_especialista.last_name}")
    # 5. Renderizar el HTML con los datos
    # Asegúrate de que tu template HTML use: <img src="{{ bg_url }}">
    html_string = render_to_string('pdf/constancia_template.html', context)

    # 6. Generar el PDF en Memoria
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        html_string, 
        dest=buffer, 
        link_callback=link_callback,
        encoding='UTF-8'
    )
    
    # DEBUG LOGS (Verás esto en la terminal si algo falla)
    print(f"DEBUG: PDF Generado. Errores: {pisa_status.err}")
    if not bg_url: print("ALERTA: No se pudo cargar el fondo en Base64")

    if pisa_status.err:
        return None
        
    return buffer.getvalue()

   
@login_required
def generar_pdf_constancia_view(request, pk):
    constancia = get_object_or_404(Constancia, pk=pk)
    pdf_file = _generar_pdf_bytes(constancia)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"constancia_{constancia.participante.nombre_completo}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response




@login_required
def enviar_constancias_masivo_view(request):
    if request.method == 'POST':
        # Obtenemos la lista de IDs seleccionados en el historial
        constancias_ids = request.POST.getlist('constancias_seleccionadas')
        
        if not constancias_ids:
            messages.warning(request, "Por favor, selecciona al menos una constancia.")
            return redirect('users:historial_constancias')

        enviados = 0
        for c_id in constancias_ids:
            constancia = get_object_or_404(Constancia, pk=c_id)
            email_destino = constancia.participante.email

            if email_destino:
                # Generar el PDF en memoria
                context = {'constancia': constancia}
                html_string = render_to_string('pdf/constancia_template.html', context)
                result = io.BytesIO()
                
                # Aquí usamos pisa y link_callback sin errores
                pisa_status = pisa.pisaDocument(
                    io.BytesIO(html_string.encode("UTF-8")), 
                    result, 
                    link_callback=link_callback
                )
                
                pdf_content = result.getvalue()

                # Configurar el correo
                subject = f"Constancia: {constancia.curso.nombre}"
                body = f"Hola {constancia.participante.nombre_completo},\n\nAdjuntamos tu constancia de participación.\n\nSaludos."
                
                email = EmailMessage(
                    subject, 
                    body, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [email_destino]
                )
                
                filename = f"Constancia_{constancia.participante.nombre_completo}.pdf"
                email.attach(filename, pdf_content, 'application/pdf')
                
                try:
                    email.send()
                    enviados += 1
                except Exception as e:
                    print(f"Error enviando a {email_destino}: {e}")

        messages.success(request, f"¡Éxito! Se enviaron {enviados} correos automáticamente.")
        return redirect('users:historial_constancias')
    
    return redirect('users:historial_constancias')


def enviar_constancia_view(request, pk):
    """
    Esta es la función que Django no encontraba.
    Por ahora, solo nos redirigirá para que el sistema no falle.
    """
    # Aquí irá la lógica para enviar el correo más adelante
    messages.info(request, f"Preparando el envío de la constancia ID: {pk}")
    
    # Cambia 'nombre_de_tu_lista' por el nombre de la URL a la que quieras volver
    return redirect('users:login')


from django.utils import timezone
from datetime import timedelta

from django.views.decorators.cache import never_cache # <--- Importar esto
@never_cache
def buscador_constancias_publico(request):
    constancias = None
    email_query = None  # Usamos un nombre diferente para no confundir con el campo
    
    if request.method == 'POST':
        email_query = request.POST.get('email')
        
        # 1. Ajustamos la fecha para que cubra desde el 13 de febrero (aprox 40 días)
        hace_40_dias = timezone.now().date() - timedelta(days=40)
        
        # 2. El FILTRO CORRECTO:
        # 'participante' es el nombre del campo en el modelo Constancia
        # 'email' es el nombre del campo en tu modelo Participante
        constancias = Constancia.objects.filter(
            participante__email__iexact=email_query, 
            fecha_emision__gte=hace_40_dias
        )
        
        if not constancias.exists():
            messages.error(request, f"No se encontraron constancias recientes para: {email_query}")
            
    return render(request, 'users/buscador.html', {
        'constancias': constancias,
        'email': email_query
    })



from django.contrib.auth import logout as auth_logout

def logout_view(request):
    # 1. Limpiamos los datos específicos que guardamos en la sesión
    # (por si acaso quedaron rastros del webinar)
    request.session.flush() 
    
    # 2. Cerramos la sesión del usuario en Django
    auth_logout(request)
    
    # 3. Redirigimos al buscador público o al login
    return redirect('users:buscador_publico')

def descargar_pdf_publico(request, pk):
    # Calculamos la fecha de corte: hoy menos 20 días
    hace_40_dias = timezone.now().date() - timedelta(days=40)
    
    try:
        # IMPORTANTE: Usar la variable hace_20_dias aquí
        constancia = Constancia.objects.get(pk=pk, fecha_emision__gte=hace_40_dias)
        
        pdf_bytes = _generar_pdf_bytes(constancia)
        
        if pdf_bytes:
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            # Mejora: El nombre del archivo ahora incluye el nombre del participante
            filename = f"Constancia_{constancia.participante.nombre_completo}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            messages.error(request, "Error al generar el archivo PDF.")
            return redirect('users:buscador_publico')

    except Constancia.DoesNotExist:
        messages.error(request, "El enlace ha expirado o no es válido (máximo 20 días).")
        return redirect('users:buscador_publico')


@login_required
def crear_participante_rapido_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    form = ParticipanteForm(request.POST)
    if form.is_valid():
        participante = form.save()
        return JsonResponse({
            'ok': True,
            'id': participante.id,
            'nombre': str(participante),
        })

    errores = {campo: [str(e) for e in lista] for campo, lista in form.errors.items()}
    return JsonResponse({'ok': False, 'errores': errores}, status=400)


@login_required
def libro_paso1_subir_view(request):
    """Sube el libro de capacitaciones y detecta las sesiones (hojas)."""
    if request.method == 'POST':
        form = LibroCapacitacionesForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            anio = form.cleaned_data['anio']
            minima = float(form.cleaned_data['calificacion_minima'])
 
            try:
                sesiones = importadores.analizar_libro(
                    archivo.read(), anio=anio, calificacion_minima=minima
                )
            except Exception:
                messages.error(
                    request,
                    "No se pudo leer el archivo. Verifica que sea un Excel (.xlsx) válido."
                )
                return redirect('users:libro_paso1')
 
            if not sesiones:
                messages.error(
                    request,
                    "No se detectó ninguna sesión. Revisa que las hojas tengan "
                    "las columnas 'Nombre' y 'Correo'."
                )
                return redirect('users:libro_paso1')
 
            # Serializamos para la sesión de Django (las fechas van como texto).
            serializado = []
            for s in sesiones:
                serializado.append({
                    'hoja': s['hoja'],
                    'curso': s['curso'],
                    'fecha': s['fecha'].isoformat() if s['fecha'] else None,
                    'duracion_horas': s['duracion_horas'] or 1.0,
                    'modalidad': s['modalidad'],
                    'inscritos': s['inscritos'],
                    'con_calificacion': s['con_calificacion'],
                    'aprobados': s['aprobados'],
                    'reprobados': s['reprobados'],
                    'sin_correo': s['sin_correo'],
                    'estado': s['estado'],
                    'seleccionable': (
                        s['estado'] == 'listo' and s['aprobados'] > 0 and s['fecha'] is not None
                    ),
                    'personas': [
                        {
                            'nombre_completo': a['nombre_completo'],
                            'email': a['email'],
                            'institucion': a['institucion'],
                            'calificacion': a['calificacion'],
                            'aprueba': a['aprueba'],
                        }
                        for a in s['asistentes']
                    ],
                })
 
            request.session['libro_sesiones'] = serializado
            request.session['libro_config'] = {
                'calificacion_minima': minima,
                'firma_especialista_id': form.cleaned_data['firma_especialista'].id,
            }
            return redirect('users:libro_paso2')
    else:
        form = LibroCapacitacionesForm()
 
    return render(request, 'users/libro_paso1_subir.html', {'form': form})
 
 
@login_required


@login_required
def libro_paso2_seleccionar_view(request):
    """Elige qué sesiones procesar y genera las constancias."""
    sesiones = request.session.get('libro_sesiones')
    config = request.session.get('libro_config')

    if not sesiones or not config:
        messages.error(request, "No hay datos para procesar. Sube el archivo de nuevo.")
        return redirect('users:libro_paso1')

    if request.method == 'POST':
        elegidas = request.POST.getlist('hojas')
        if not elegidas:
            messages.error(request, "Selecciona al menos una sesión.")
            return redirect('users:libro_paso2')

        firma_especialista = Evaluador.objects.filter(
            id=config['firma_especialista_id']
        ).first()
        firma_gerente = Evaluador.objects.filter(es_gerente=True).first()

        total = 0
        omitidas = 0
        repetidas = 0
        resumen = []

        try:
            with transaction.atomic():
                for s in sesiones:
                    if s['hoja'] not in elegidas or not s['seleccionable']:
                        continue

                    # --- 1) Quitar repetidos dentro de la hoja ---
                    unicos = {}
                    for p in s['personas']:
                        if not p['aprueba'] or not p['email']:
                            continue
                        clave = p['email'].strip().lower()
                        anterior = unicos.get(clave)
                        if anterior is None:
                            unicos[clave] = p
                        else:
                            repetidas += 1
                            nueva = p.get('calificacion') or 0
                            vieja = anterior.get('calificacion') or 0
                            if nueva > vieja:
                                unicos[clave] = p

                    if not unicos:
                        continue

                    # --- 2) Un curso por hoja, reutilizable ---
                    curso, _ = Curso.objects.get_or_create(nombre=s['curso'])
                    generadas = 0

                    for email, p in unicos.items():
                        participante, creado = Participante.objects.get_or_create(
                            email=email,
                            defaults={
                                'nombre_completo': p['nombre_completo'],
                                'institucion_id': None,
                            }
                        )
                        if not creado:
                            participante.nombre_completo = p['nombre_completo']
                            participante.save()

                        # --- 3) No duplicar constancias ya existentes ---
                        constancia, nueva = Constancia.objects.get_or_create(
                            participante=participante,
                            curso=curso,
                            fecha_inicio=s['fecha'],
                            defaults={
                                'fecha_termino': s['fecha'],
                                'duracion_en_horas': s['duracion_horas'],
                                'firma_gerente': firma_gerente,
                                'firma_especialista': firma_especialista,
                                'codigo_verificacion': str(uuid.uuid4()).split('-')[0].upper(),
                                'es_webinar': True,
                                'tipo': 'teorica',
                            }
                        )
                        if nueva:
                            generadas += 1
                        else:
                            omitidas += 1

                    total += generadas
                    resumen.append(f"{s['curso']} ({generadas})")

            request.session.pop('libro_sesiones', None)
            request.session.pop('libro_config', None)

            texto = f"Se generaron {total} constancias de {len(resumen)} sesión(es): " \
                    + ", ".join(resumen)
            if omitidas:
                texto += f" · {omitidas} ya existían y se omitieron"
            if repetidas:
                texto += f" · {repetidas} fila(s) repetida(s) en el Excel"
            messages.success(request, texto)
            return redirect('users:historial_constancias')

        except Exception as e:
            messages.error(request, f"Error al generar las constancias: {str(e)}")
            return redirect('users:libro_paso2')

    listas = [s for s in sesiones if s['seleccionable']]
    context = {
        'sesiones': sesiones,
        'total_disponibles': sum(s['aprobados'] for s in listas),
        'minima': config['calificacion_minima'],
    }
    return render(request, 'users/libro_paso2_seleccionar.html', context)