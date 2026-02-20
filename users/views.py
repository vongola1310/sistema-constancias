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
from django.conf import settings
from .models import Participante, Curso, Constancia

from .forms import (
    EvaluadorCreationForm, ProfilePhotoForm, SignatureForm, 
    CursoForm, ParticipanteForm, InstitucionForm, LoteConstanciaForm,
    WebinarStep1Form, EncuestaForm
)
from .models import (
    Constancia, Evaluador, Curso, Participante, Institucion,
    EncuestaRespuesta, LeadVenta
)

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
                        'es_webinar': False
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

@login_required
def webinar_paso1_subir_view(request):
    if request.method == 'POST':
        form = WebinarStep1Form(request.POST, request.FILES)
        if form.is_valid():
            # Guardamos datos del curso
            request.session['webinar_event_data'] = {
                'curso_nombre': form.cleaned_data['curso_nombre'],
                'fecha_inicio': form.cleaned_data['fecha_inicio'].isoformat(),
                'fecha_termino': form.cleaned_data['fecha_termino'].isoformat(),
                'duracion_en_horas': float(form.cleaned_data['duracion_en_horas']),
                'firma_especialista_id': form.cleaned_data['firma_especialista'].id,
            }

            archivo_csv = form.cleaned_data['archivo_csv']
            raw_data = archivo_csv.read()
            decoded_file = None
            
            # Intentar decodificar (GoToWebinar suele usar UTF-16 o UTF-8 con BOM)
            for encoding in ['utf-8-sig', 'utf-16']:
                try:
                    decoded_file = raw_data.decode(encoding).splitlines()
                    break
                except UnicodeDecodeError:
                    continue

            if decoded_file is None:
                messages.error(request, "Error de codificación. Prueba guardar el Excel como 'CSV UTF-8'.")
                return redirect('users:webinar_paso1')
            
            reader = csv.reader(decoded_file, delimiter='\t')
            next(reader, None) # Saltar encabezado
            next(reader, None)  # Saltar fila 2 (nombres de columnas: "Attendee", "Duration"...)
            participantes_raw = {}
            for row in reader:
                try:
                    # Basado en tu archivo: 8:Nombre, 9:Apellido, 10:Institución, 11:Email, 14:Duración
                    nombre_completo = f"{row[8]} {row[9]}".strip()
                    institucion = row[10].strip() if row[10] else "N/A"
                    email = row[11].strip().lower()
                    minutos = int(row[14].split()[0])
                    
                    if not email: continue

                    if email not in participantes_raw:
                        participantes_raw[email] = {
                            'nombre_completo': nombre_completo,
                            'institucion': institucion,
                            'duracion_total': 0
                        }
                    participantes_raw[email]['duracion_total'] += minutos
                except (IndexError, ValueError):
                    continue

            # Clasificación
            calificados = []
            no_calificados = []
            for email, data in participantes_raw.items():
                info = {
                    'nombre_completo': data['nombre_completo'],
                    'email': email,
                    'institucion': data['institucion'],
                    'duracion_total': data['duracion_total']
                }
                if data['duracion_total'] >= 30:
                    calificados.append(info)
                else:
                    no_calificados.append(info)

            request.session['webinar_participantes_calificados'] = calificados
            request.session['webinar_participantes_no_calificados'] = no_calificados
            return redirect('users:webinar_paso2')
            
    return render(request, 'users/webinar_paso1_subir.html', {'form': WebinarStep1Form()})

from django.db import transaction
from .models import Participante, Curso, Constancia
from .models import Participante, Curso, Constancia, Evaluador
@login_required
def webinar_paso2_previsualizar_view(request):
    event_data = request.session.get('webinar_event_data')
    participantes = request.session.get('webinar_participantes_calificados')
    no_calificados = request.session.get('webinar_participantes_no_calificados')

    if not event_data or participantes is None:
        messages.error(request, "No hay datos para procesar.")
        return redirect('users:webinar_paso1')

    # --- INICIO DE LA LÓGICA POST ---
    if request.method == 'POST':
        try:
            with transaction.atomic():
                
                # 1. Crear el Curso en la Base de Datos
                curso = Curso.objects.create(
                    nombre=event_data['curso_nombre'],
                )

                # 2. Obtener los Firmantes (Evaluador)
                # Especialista: Usamos el ID que guardaste en el paso 1
                firma_e_id = event_data.get('firma_especialista_id')
                firma_especialista = Evaluador.objects.filter(id=firma_e_id).first() if firma_e_id else None

                # Gerente: Buscamos al Evaluador que tenga es_gerente=True (según tu models.py)
                firma_gerente = Evaluador.objects.filter(es_gerente=True).first()

                # 3. Crear Participantes y sus Constancias
                for p_data in participantes:
                    participante, created = Participante.objects.get_or_create(
                        email=p_data['email'],
                        defaults={
                            'nombre_completo': p_data['nombre_completo'],
                            'institucion_id': None  # Asumimos None si es texto libre, ajusta si vinculas al modelo Institucion
                        }
                    )

                    if not created:
                        participante.nombre_completo = p_data['nombre_completo']
                        participante.save()

                    import uuid # Asegúrate de que import uuid esté arriba en el archivo
                    nuevo_codigo = str(uuid.uuid4()).split('-')[0].upper()

                    # Finalmente, creamos la constancia con los datos exactos que pide tu modelo
                    Constancia.objects.create(
                        participante=participante,
                        curso=curso,
                        fecha_inicio=event_data['fecha_inicio'],
                        fecha_termino=event_data['fecha_termino'],
                        duracion_en_horas=event_data['duracion_en_horas'],
                        firma_gerente=firma_gerente,
                        firma_especialista=firma_especialista,
                        codigo_verificacion=nuevo_codigo,
                        es_webinar=True # Marcamos que viene del flujo de Webinar
                    )

            # 4. Limpiar la sesión 
            del request.session['webinar_event_data']
            del request.session['webinar_participantes_calificados']
            del request.session['webinar_participantes_no_calificados']

            # 5. Mensaje de éxito y redirección
            messages.success(request, f"¡Éxito! Se generaron {len(participantes)} constancias correctamente.")
            return redirect('users:historial_constancias')

        except Exception as e:
            messages.error(request, f"Hubo un error al generar las constancias: {str(e)}")
            return redirect('users:webinar_paso2')


    # Si es GET (solo cargar la página), muestra el HTML
    context = {
        'participantes': participantes,
        'no_calificados': no_calificados,
        'evento': event_data,
    }
    return render(request, 'users/webinar_paso2_previsualizar.html', context)

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
    email_busqueda = request.POST.get('email', '').strip().lower()
    constancias = []
    
    if request.method == 'POST' and email_busqueda:
        hace_7_dias = timezone.now().date() - timedelta(days=7)
        constancias = Constancia.objects.filter(
            participante__email__iexact=email_busqueda,
            fecha_emision__gte=hace_7_dias
        ).order_by('-fecha_emision')

        if constancias.count() == 1:
            # En lugar de redireccionar a otra vista, generamos los bytes aquí mismo
            c = constancias.first()
            pdf_bytes = _generar_pdf_bytes(c) # Usamos tu función auxiliar que ya tenemos
            
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Constancia_{c.codigo_verificacion}.pdf"'
            return response
        
        if not constancias.exists():
            messages.info(request, "No se encontraron constancias vigentes para este correo.")

    return render(request, 'public/buscador.html', {'constancias': constancias, 'email': email_busqueda})


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
    hace_7_dias = timezone.now().date() - timedelta(days=7)
    # Buscamos la constancia pero SOLO si es de los últimos 7 días
    try:
        constancia = Constancia.objects.get(pk=pk, fecha_emision__gte=hace_7_dias)
        pdf_bytes = _generar_pdf_bytes(constancia)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Constancia.pdf"'
        return response
    except Constancia.DoesNotExist:
        messages.error(request, "El enlace ha expirado o no es válido.")
        return redirect('users:buscador_publico')