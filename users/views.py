import os
import uuid
import io
import base64
import mimetypes
import zipfile
import pdfkit
import openpyxl
import csv
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

@login_required
def webinar_paso2_previsualizar_view(request):
    event_data = request.session.get('webinar_event_data')
    participantes = request.session.get('webinar_participantes_calificados')
    no_calificados = request.session.get('webinar_participantes_no_calificados')

    if not event_data or participantes is None:
        messages.error(request, "No hay datos para procesar.")
        return redirect('users:webinar_paso1')

    # ... (Aquí va tu lógica de POST para guardar en DB que ya tienes) ...

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
from django.conf import settings

def _imagen_a_base64(path):
    """Convierte una imagen local a string base64 para incrustar en HTML."""
    if not path or not os.path.exists(path):
        return ""
    
    ext = os.path.splitext(path)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
    }
    mime = mime_types.get(ext, 'image/png')
    
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    
    return f"data:{mime};base64,{data}"


def _generar_pdf_bytes(constancia):

    # 1. Convertir imágenes a Base64
    bg_path = finders.find('images/fondo_constancia.png')
    bg_url = _imagen_a_base64(bg_path)

    firma_g_url = (
        _imagen_a_base64(constancia.firma_gerente.firma_digital.path)
        if constancia.firma_gerente else ""
    )
    firma_e_url = (
        _imagen_a_base64(constancia.firma_especialista.firma_digital.path)
        if constancia.firma_especialista else ""
    )

    # 2. Formateo de datos
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    f = constancia.fecha_termino
    fecha_texto = f"{f.day} de {meses[f.month]} de {f.year}" if f else ""
    duracion_formateada = f"{int(constancia.duracion_en_horas):02d}" if constancia.duracion_en_horas else "00"

    # 3. Contexto del template
    context = {
        'constancia': constancia,
        'bg_url': bg_url,
        'firma_g_url': firma_g_url,
        'firma_e_url': firma_e_url,
        'fecha_texto': fecha_texto,
        'duracion_formateada': duracion_formateada,
    }

    # 4. Renderizar el HTML
    html_string = render_to_string('pdf/constancia_template.html', context)
    
    print(f"DEBUG HTML COMPLETO:\n{html_string}")

    with open(r'C:\Users\PAlvaro\Documents\debug_constancia.html', 'w', encoding='utf-8') as f:f.write(html_string)

    print(f"DEBUG html_string longitud: {len(html_string)}")
    print(f"DEBUG bg_url tiene datos: {bool(context['bg_url'])}")
    print(f"DEBUG constancia.participante: {constancia.participante}")
    print(f"DEBUG constancia.curso: {constancia.curso}")
    print(f"DEBUG fecha_texto: {fecha_texto}")

    # 5. Guardar HTML en archivo temporal y generar PDF desde archivo
    tmp_html = None
    try:
        # Crear archivo temporal para el HTML
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.html',
            delete=False,
            encoding='utf-8'
        ) as tmp:
            tmp.write(html_string)
            tmp_html = tmp.name

        # Configuración de wkhtmltopdf
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

        options = {
            'page-size': 'Letter',
            'orientation': 'Landscape',
            'margin-top': '0', 'margin-right': '0',
            'margin-bottom': '0', 'margin-left': '0',
            'encoding': "UTF-8",
            'no-outline': None,
            'quiet': '',
            'zoom': '1.38',
        }

        # Generar PDF desde archivo (no desde string)
        pdf_bytes = pdfkit.from_file(tmp_html, False, configuration=config, options=options)
        return pdf_bytes

    finally:
        # Limpiar archivo temporal siempre, aunque haya error
        if tmp_html and os.path.exists(tmp_html):
            os.unlink(tmp_html)

   
@login_required
def generar_pdf_constancia_view(request, pk):
    constancia = get_object_or_404(Constancia, pk=pk)
    pdf_file = _generar_pdf_bytes(constancia)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"constancia_{constancia.participante.nombre_completo}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# 1. FUNCIÓN DE APOYO (Debe ir arriba para que no de error de "not defined")
def link_callback(uri, rel):
    """
    Convierte URLs de HTML a rutas absolutas para xhtml2pdf.
    """
    result = finders.find(uri)
    if result:
        if not isinstance(result, (list, tuple)):
            result = [result]
        result = list(os.path.realpath(path) for path in result)
        path = result[0]
    else:
        sUrl = settings.STATIC_URL
        mUrl = settings.MEDIA_URL
        if uri.startswith(mUrl):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(mUrl, ""))
        elif uri.startswith(sUrl):
            path = os.path.join(settings.STATIC_ROOT, uri.replace(sUrl, ""))
        else:
            return uri
    if not os.path.isfile(path):
        return uri
    return path

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