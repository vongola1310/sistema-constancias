import os
import uuid
import io
import base64
import mimetypes
import zipfile
import pdfkit
import openpyxl
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from datetime import timedelta

from .forms import (
    EvaluadorCreationForm, ProfilePhotoForm, SignatureForm, 
    CursoForm, ParticipanteForm, InstitucionForm, LoteConstanciaForm,
    WebinarUploadForm
)
from .models import Constancia, Evaluador, Curso, Participante, Institucion

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
    # Obtenemos la fecha actual para hacer las comparaciones
    hoy = timezone.now().date()
    
    # Buscamos las constancias que ya vencieron
    # Filtramos por fecha_vencimiento menor a hoy y que no sean de webinar
    constancias_vencidas = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__lt=hoy
    )
    
    # Buscamos constancias que vencerán en los próximos 30 días
    # Primero calculamos la fecha límite (hoy + 30 días)
    limite_30_dias = hoy + timedelta(days=30)
    # Luego filtramos las que están entre hoy y esa fecha límite
    constancias_por_vencer = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_30_dias
    )

    # Preparamos el contexto para enviarlo a la plantilla HTML
    context = {
        'user': request.user,
        'constancias_vencidas': constancias_vencidas,
        'constancias_por_vencer': constancias_por_vencer,
    }
    return render(request, 'users/dashboard.html', context)
    # Obtenemos la fecha actual para hacer las comparaciones
    hoy = timezone.now().date()
    
    # Buscamos las constancias que ya vencieron
    # Filtramos por fecha_vencimiento menor a hoy y que no sean de webinar
    constancias_vencidas = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__lt=hoy
    )
    
    # Buscamos constancias que vencerán en los próximos 30 días
    # Primero calculamos la fecha límite (hoy + 30 días)
    limite_30_dias = hoy + timedelta(days=30)
    # Luego filtramos las que están entre hoy y esa fecha límite
    constancias_por_vencer = Constancia.objects.filter(
        es_webinar=False,
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_30_dias
    )

    # Preparamos el contexto para enviarlo a la plantilla HTML
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

# --- VISTAS DE CREACIÓN DE OBJETOS ---

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
def crear_participante_view(request):
    if request.method == 'POST':
        form = ParticipanteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡El participante ha sido registrado exitosamente!')
            return redirect('users:dashboard')
    else:
        form = ParticipanteForm()
    context = {'form': form}
    return render(request, 'users/crear_participante.html', context)

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
                # Usamos get_or_create para evitar duplicados exactos
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
                        'es_webinar': False  # Marcamos estas como NO de webinar
                    }
                )
                if created:
                    # Calculamos la fecha de vencimiento (1 año después de la emisión)
                    constancia.fecha_vencimiento = constancia.fecha_emision + relativedelta(years=1)
                    constancia.save() # Guardamos la constancia con la nueva fecha
                    constancias_creadas += 1
            
            messages.success(request, f'¡Se crearon {constancias_creadas} constancias de curso exitosamente!')
            return redirect('users:historial_constancias')
    else:
        form = LoteConstanciaForm()
    
    context = {'form': form}
    return render(request, 'users/crear_lote_constancias.html', context)

@login_required
def subir_webinar_view(request):
    if request.method == 'POST':
        form = WebinarUploadForm(request.POST, request.FILES)
        if form.is_valid():
            archivo_excel = request.FILES['archivo_excel']
            curso_nombre = form.cleaned_data['curso_nombre']
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_termino = form.cleaned_data['fecha_termino']
            duracion = form.cleaned_data['duracion_en_horas']
            especialista = form.cleaned_data['firma_especialista']
            
            try:
                gerente = Evaluador.objects.get(es_gerente=True)
            except Evaluador.DoesNotExist:
                messages.error(request, 'Error: No se ha designado un gerente en el sistema.')
                return redirect('users:dashboard')

            curso, _ = Curso.objects.get_or_create(nombre=curso_nombre)

            # --- LÓGICA FINAL Y ROBUSTA ---
            participantes_a_procesar = []
            try:
                workbook = openpyxl.load_workbook(archivo_excel)
                sheet = workbook.active
                for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not row[0] or not row[1]:
                        continue

                    participantes_a_procesar.append({
                        'nombre': str(row[0]).strip(),
                        'email': str(row[1]).strip().lower(),
                        'titulo': str(row[2]).strip() if row[2] else "",
                        'institucion': str(row[3]).strip() if row[3] else "",
                        'fila': i,
                    })
            except Exception as e:
                messages.error(request, f"Error al leer el archivo de Excel: {e}")
                return redirect('users:subir_webinar')

            constancias_creadas = 0
            constancias_encontradas = 0
            errores = []
            
            for data in participantes_a_procesar:
                try:
                    institucion = None
                    if data['institucion']:
                        institucion, _ = Institucion.objects.get_or_create(nombre__iexact=data['institucion'], defaults={'nombre': data['institucion']})

                    participante, p_created = Participante.objects.update_or_create(
                        email__iexact=data['email'],
                        defaults={'email': data['email'], 'nombre_completo': data['nombre'], 'titulo': data['titulo'], 'institucion': institucion}
                    )
                    
                    constancia, c_created = Constancia.objects.get_or_create(
                        participante=participante, curso=curso, fecha_inicio=fecha_inicio,
                        defaults={
                            'fecha_termino': fecha_termino, 'duracion_en_horas': duracion,
                            'firma_gerente': gerente, 'firma_especialista': especialista,
                            'codigo_verificacion': str(uuid.uuid4()).split('-')[0].upper(),
                            'es_webinar': True
                        }
                    )
                    if c_created:
                        constancias_creadas += 1
                    else:
                        constancias_encontradas +=1
                except Exception as e:
                    errores.append(f"Fila {data['fila']}: {e}")

            # --- MENSAJES DE ÉXITO MEJORADOS ---
            mensaje_exito = f'Proceso completado. Se crearon {constancias_creadas} nuevas constancias.'
            if constancias_encontradas > 0:
                mensaje_exito += f' Se encontraron y omitieron {constancias_encontradas} que ya existían.'
            messages.success(request, mensaje_exito)
            
            if errores:
                messages.warning(request, f'Se encontraron problemas en {len(errores)} filas.')
            
            return redirect('users:historial_constancias')
    else:
        form = WebinarUploadForm()

    context = {'form': form}
    return render(request, 'users/subir_webinar.html', context)
    

@login_required
def historial_constancias_view(request):
  # Obtenemos el parámetro 'tipo' de la URL. Si no existe, no aplicamos ningún filtro.
    filtro_tipo = request.GET.get('tipo', None)
    
    # Empezamos con el listado de todas las constancias.
    lista_constancias = Constancia.objects.all()
    
    # Aplicamos el filtro si el usuario seleccionó uno.
    if filtro_tipo == 'webinar':
        # Filtramos para mostrar solo las constancias marcadas como 'es_webinar = True'.
        lista_constancias = lista_constancias.filter(es_webinar=True)
    elif filtro_tipo == 'curso':
        # Filtramos para mostrar solo las que NO están marcadas como webinar.
        lista_constancias = lista_constancias.filter(es_webinar=False)
    
    # Ordenamos el resultado final para que las más recientes aparezcan primero.
    constancias = lista_constancias.order_by('-fecha_emision')
    
    # Preparamos el contexto para enviarlo a la plantilla HTML.
    context = {
        'constancias': constancias,
        'filtro_activo': filtro_tipo # Pasamos el filtro actual para poder resaltar el botón correcto.
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

# --- LÓGICA DE GENERACIÓN DE PDF Y ZIP ---

def _generar_pdf_bytes(constancia):
    """
    Función auxiliar que toma una constancia y devuelve los bytes de su PDF.
    """
    # Lógica para Incrustar Imágenes en Base64
    bg_image_base64, bg_image_mime_type = "", ""
    if finders.find('images/fondo_constancia.png'):
        path = finders.find('images/fondo_constancia.png')
        bg_image_mime_type, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            bg_image_base64 = base64.b64encode(f.read()).decode('utf-8')

    firma_gerente_base64, firma_gerente_mime_type = "", ""
    if constancia.firma_gerente and constancia.firma_gerente.firma_digital:
        path = constancia.firma_gerente.firma_digital.path
        firma_gerente_mime_type, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            firma_gerente_base64 = base64.b64encode(f.read()).decode('utf-8')

    firma_especialista_base64, firma_especialista_mime_type = "", ""
    if constancia.firma_especialista and constancia.firma_especialista.firma_digital:
        path = constancia.firma_especialista.firma_digital.path
        firma_especialista_mime_type, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            firma_especialista_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    context = {
        'constancia': constancia, 'bg_image_base64': bg_image_base64,
        'bg_image_mime_type': bg_image_mime_type, 'firma_gerente_base64': firma_gerente_base64,
        'firma_gerente_mime_type': firma_gerente_mime_type, 'firma_especialista_base64': firma_especialista_base64,
        'firma_especialista_mime_type': firma_especialista_mime_type,
    }
    
    html_string = render_to_string('pdf/constancia_template.html', context)
    
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    options = {
        'enable-local-file-access': None, 'page-size': 'Letter',
        'orientation': 'Landscape', 'margin-top': '0', 'margin-right': '0',
        'margin-bottom': '0', 'margin-left': '0',
    }
    
    return pdfkit.from_string(html_string, False, configuration=config, options=options)

@login_required
def generar_pdf_constancia_view(request, pk):
    constancia = get_object_or_404(Constancia, pk=pk)
    pdf_file = _generar_pdf_bytes(constancia)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"constancia_{constancia.participante.nombre_completo}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

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
    # 1. Buscamos al participante específico usando el 'pk' (ID) de la URL
    participante = get_object_or_404(Participante, pk=pk)
    
    # 2. Usamos la relación inversa para encontrar todas las constancias de ese participante
    constancias = participante.constancia_set.all().order_by('-fecha_emision')
    
    context = {
        'participante': participante,
        'constancias': constancias,
    }
    return render(request, 'users/historial_participante.html', context)