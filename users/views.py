import os
import uuid
import io
import base64
import mimetypes
import pdfkit
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.http import HttpResponse
import openpyxl

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
    context = {'user': request.user}
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
                constancia, created = Constancia.objects.get_or_create(
                    participante=participante,
                    curso=curso,
                    fecha_inicio=fecha_inicio,
                    defaults={
                        'fecha_termino': fecha_termino,
                        'duracion_en_horas': duracion,
                        'firma_gerente': gerente,
                        'firma_especialista': especialista,
                        'codigo_verificacion': str(uuid.uuid4()).split('-')[0].upper()
                    }
                )
                if created:
                    constancias_creadas += 1
            messages.success(request, f'¡Se crearon {constancias_creadas} constancias exitosamente!')
            return redirect('users:historial_constancias')
    else:
        form = LoteConstanciaForm()
    context = {'form': form}
    return render(request, 'users/crear_lote_constancias.html', context)

@login_required
def historial_constancias_view(request):
    constancias = Constancia.objects.all().order_by('-fecha_emision')
    context = {'constancias': constancias}
    return render(request, 'users/historial_constancias.html', context)

@login_required
def generar_pdf_constancia_view(request, pk):
    constancia = get_object_or_404(Constancia, pk=pk)
    
    # Lógica para Incrustar Imágenes en Base64
    bg_image_base64, bg_image_mime_type = "", ""
    try:
        background_path = finders.find('images/fondo_constancia.png')
        if background_path:
            bg_image_mime_type, _ = mimetypes.guess_type(background_path)
            with open(background_path, "rb") as image_file:
                bg_image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error al cargar imagen de fondo: {e}")

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
        'constancia': constancia,
        'bg_image_base64': bg_image_base64,
        'bg_image_mime_type': bg_image_mime_type,
        'firma_gerente_base64': firma_gerente_base64,
        'firma_gerente_mime_type': firma_gerente_mime_type,
        'firma_especialista_base64': firma_especialista_base64,
        'firma_especialista_mime_type': firma_especialista_mime_type,
    }
    
    html_string = render_to_string('pdf/constancia_template.html', context)
    
    # --- Lógica de PDFkit ---
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    options = {
        'enable-local-file-access': None, 'page-size': 'Letter',
        'orientation': 'Landscape', 'margin-top': '0', 'margin-right': '0',
        'margin-bottom': '0', 'margin-left': '0',
    }
    
    pdf_file = pdfkit.from_string(html_string, False, configuration=config, options=options)
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"constancia_{constancia.participante.nombre_completo}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def subir_webinar_view(request):
    if request.method == 'POST':
        form = WebinarUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # ... (la primera parte para obtener datos del form no cambia) ...
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
            emails_ya_vistos = set()
            try:
                workbook = openpyxl.load_workbook(archivo_excel)
                sheet = workbook.active
                for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not row[0] or not row[1]:
                        continue # Saltamos filas si no tienen nombre o email

                    email = str(row[1]).strip().lower()
                    
                    # Si ya vimos este email en este archivo, lo ignoramos
                    if email in emails_ya_vistos:
                        continue

                    participantes_a_procesar.append({
                        'nombre': str(row[0]).strip(),
                        'email': email,
                        'titulo': str(row[2]).strip() if row[2] else "",
                        'institucion': str(row[3]).strip() if row[3] else "",
                        'fila': i,
                    })
                    emails_ya_vistos.add(email) # Lo añadimos a la memoria
            except Exception as e:
                messages.error(request, f"Error al leer el archivo de Excel: {e}")
                return redirect('users:subir_webinar')

            constancias_creadas = 0
            errores = []
            
            for data in participantes_a_procesar:
                try:
                    institucion = None
                    if data['institucion']:
                        institucion, _ = Institucion.objects.get_or_create(nombre__iexact=data['institucion'], defaults={'nombre': data['institucion']})

                    participante, _ = Participante.objects.update_or_create(
                        email__iexact=data['email'],
                        defaults={'email': data['email'], 'nombre_completo': data['nombre'], 'titulo': data['titulo'], 'institucion': institucion}
                    )
                    
                    _, created = Constancia.objects.get_or_create(
                        participante=participante, curso=curso, fecha_inicio=fecha_inicio,
                        defaults={
                            'fecha_termino': fecha_termino, 'duracion_en_horas': duracion,
                            'firma_gerente': gerente, 'firma_especialista': especialista,
                            'codigo_verificacion': str(uuid.uuid4()).split('-')[0].upper(),
                            'es_webinar': True
                        }
                    )
                    if created:
                        constancias_creadas += 1
                except Exception as e:
                    errores.append(f"Fila {data['fila']}: {e}")

            messages.success(request, f'Proceso completado. Se crearon {constancias_creadas} nuevas constancias.')
            if errores:
                messages.warning(request, f'Se encontraron problemas en {len(errores)} filas.')
            
            return redirect('users:historial_constancias')
    else:
        form = WebinarUploadForm()

    context = {'form': form}
    return render(request, 'users/subir_webinar.html', context)

@login_required
def borrar_constancias_view(request):
    if request.method == 'POST':
        # Obtenemos la lista de todos los IDs que vienen de los checkboxes
        ids_a_borrar = request.POST.getlist('constancia_ids')
        
        if ids_a_borrar:
            # Usamos filter(pk__in=...) para encontrar todos los objetos con esos IDs y los borramos
            Constancia.objects.filter(pk__in=ids_a_borrar).delete()
            messages.success(request, f"Se eliminaron {len(ids_a_borrar)} constancias exitosamente.")
        else:
            messages.warning(request, "No se seleccionó ninguna constancia para eliminar.")
            
    # Redirigimos de vuelta al historial
    return redirect('users:historial_constancias')