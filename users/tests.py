from datetime import date
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.core import mail
from django.db import IntegrityError
from django.urls import reverse
from pypdf import PdfReader

from .fechas import formatear_fechas, leer_fechas_excel, leer_fechas_texto
from .importadores import analizar_libro
from .models import Constancia, Curso, Evaluador, Institucion, Participante
from .views import _generar_pdf_bytes


class EditarConstanciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gerente = Evaluador.objects.create_user(
            username='gerente', first_name='Gerente', last_name='Prueba', es_gerente=True
        )
        cls.especialista = Evaluador.objects.create_user(
            username='firma-corregida', first_name='Especialista', last_name='Corregido'
        )
        cls.participante = Participante.objects.create(
            nombre_completo='Nombre con error', email='original@example.com'
        )
        cls.institucion = Institucion.objects.create(nombre='Institución corregida')
        cls.curso = Curso.objects.create(nombre='Evento original')
        cls.constancia = Constancia.objects.create(
            participante=cls.participante, curso=cls.curso,
            fecha_inicio=date(2026, 9, 8), fecha_termino=date(2026, 9, 10),
            fechas_evento=['2026-09-08', '2026-09-10'], duracion_en_horas=12,
            firma_gerente=cls.gerente, firma_especialista=cls.gerente,
            codigo_verificacion='ORIGINAL', tipo='teorica', es_webinar=True,
        )

    def setUp(self):
        self.client.force_login(self.gerente)
        self.url = reverse('users:editar_constancia', args=[self.constancia.pk])

    def datos(self, **cambios):
        datos = {
            'participante-nombre_completo': 'María Fernanda López García',
            'participante-email': 'corregida@example.com',
            'participante-titulo': 'Dr.',
            'participante-institucion': self.institucion.pk,
            'constancia-curso_nombre': 'Evento corregido',
            'constancia-tipo': 'curso',
            'constancia-fecha_inicio': '2026-10-01',
            'constancia-fecha_termino': '2026-10-03',
            'constancia-fechas_evento': '2026-10-03, 2026-10-01\n2026-10-03',
            'constancia-duracion_en_horas': '7.5',
            'constancia-firma_gerente': self.gerente.pk,
            'constancia-firma_especialista': self.especialista.pk,
            'constancia-fecha_vencimiento': '2027-10-03',
            'constancia-codigo_verificacion': 'CORREGIDO',
        }
        datos.update(cambios)
        return datos

    def comprobar_sin_cambios(self):
        self.participante.refresh_from_db()
        self.constancia.refresh_from_db()
        self.assertEqual(self.participante.nombre_completo, 'Nombre con error')
        self.assertEqual(self.participante.email, 'original@example.com')
        self.assertEqual(self.constancia.curso_id, self.curso.pk)
        self.assertEqual(self.constancia.codigo_verificacion, 'ORIGINAL')
        self.assertEqual(self.constancia.fecha_inicio, date(2026, 9, 8))

    def test_requiere_autenticacion_para_leer_y_guardar(self):
        self.client.logout()
        for metodo in (self.client.get, self.client.post):
            respuesta = metodo(self.url)
            self.assertRedirects(respuesta, reverse('users:login') + '?next=' + self.url)
        self.comprobar_sin_cambios()

    def test_formulario_muestra_datos_y_aviso_sobre_otras_constancias(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Nombre con error')
        self.assertContains(respuesta, 'Evento original')
        self.assertContains(respuesta, 'value="2026-09-08"')
        self.assertContains(respuesta, '2026-09-08\n2026-09-10')
        self.assertContains(respuesta, 'a todas sus constancias')
        self.comprobar_sin_cambios()

    def test_historial_incluye_edicion_directa_y_por_seleccion(self):
        respuesta = self.client.get(reverse('users:historial_constancias'))
        self.assertContains(respuesta, f'href="{self.url}"')
        self.assertContains(respuesta, 'id="edit-selected"')
        self.assertContains(respuesta, 'Para editar, selecciona una sola constancia.')

    def test_guarda_datos_y_las_descargas_reflejan_la_correccion(self):
        token, emision = self.constancia.token_encuesta, self.constancia.fecha_emision
        respuesta = self.client.post(self.url, self.datos())
        self.assertRedirects(respuesta, reverse('users:historial_constancias'))
        self.constancia.refresh_from_db()
        self.participante.refresh_from_db()
        self.assertEqual(self.participante.nombre_completo, 'María Fernanda López García')
        self.assertEqual(self.participante.email, 'corregida@example.com')
        self.assertEqual(self.participante.institucion_id, self.institucion.pk)
        self.assertEqual(self.participante.titulo, 'Dr.')
        self.assertEqual(self.constancia.curso.nombre, 'Evento corregido')
        self.assertEqual(self.constancia.fechas_evento, ['2026-10-01', '2026-10-03'])
        self.assertEqual(self.constancia.duracion_en_horas, Decimal('7.5'))
        self.assertEqual(self.constancia.firma_especialista_id, self.especialista.pk)
        self.assertEqual(self.constancia.fecha_vencimiento, date(2027, 10, 3))
        self.assertFalse(self.constancia.es_webinar)
        self.assertEqual(self.constancia.tipo, 'curso')
        self.assertEqual((self.constancia.token_encuesta, self.constancia.fecha_emision), (token, emision))
        self.assertEqual(Constancia.objects.count(), 1)
        for nombre in ('generar_pdf', 'descargar_pdf_publico'):
            with self.subTest(descarga=nombre):
                respuesta = self.client.get(reverse('users:' + nombre, args=[self.constancia.pk]))
                self.assertEqual(respuesta['Content-Type'], 'application/pdf')
                pdf = PdfReader(BytesIO(respuesta.content))
                self.assertEqual(len(pdf.pages), 1)
                texto = ' '.join(pdf.pages[0].extract_text().split())
                for esperado in (
                    'María Fernanda López García', 'Evento corregido',
                    '1 y 3 de octubre de 2026', '7,5 horas',
                    'Especialista Corregido', 'CORREGIDO', 'en el curso:',
                ):
                    self.assertIn(esperado, texto)
                self.assertNotIn('Nombre con error', texto)

    def test_correccion_personal_compartida_y_evento_individual(self):
        otra = Constancia.objects.create(
            participante=self.participante, curso=self.curso,
            fecha_inicio=date(2026, 8, 1), fecha_termino=date(2026, 8, 1),
            duracion_en_horas=2, firma_gerente=self.gerente,
            firma_especialista=self.gerente, codigo_verificacion='OTRA',
        )
        self.client.post(self.url, self.datos())
        otra.refresh_from_db()
        self.curso.refresh_from_db()
        self.assertEqual(otra.participante.nombre_completo, 'María Fernanda López García')
        self.assertEqual(otra.curso.nombre, 'Evento original')
        self.assertEqual(otra.fecha_inicio, date(2026, 8, 1))
        self.assertEqual(otra.duracion_en_horas, 2)
        self.assertEqual(self.curso.nombre, 'Evento original')

    def test_errores_de_campos_no_guardan_cambios_parciales(self):
        casos = [
            ('participante-email', 'correo-invalido', 'participante_form', 'email'),
            ('participante-nombre_completo', '', 'participante_form', 'nombre_completo'),
            ('constancia-fecha_termino', '2026-09-01', 'constancia_form', 'fecha_termino'),
            ('constancia-fechas_evento', '2026-02-30', 'constancia_form', 'fechas_evento'),
            ('constancia-fechas_evento', '2026-10-02', 'constancia_form', 'fechas_evento'),
            ('constancia-duracion_en_horas', '0', 'constancia_form', 'duracion_en_horas'),
            ('constancia-fecha_vencimiento', '2026-09-01', 'constancia_form', 'fecha_vencimiento'),
        ]
        for campo, valor, formulario, campo_error in casos:
            with self.subTest(campo=campo, valor=valor):
                respuesta = self.client.post(self.url, self.datos(**{campo: valor}))
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo_error, respuesta.context[formulario].errors)
                self.comprobar_sin_cambios()
                self.assertFalse(Curso.objects.filter(nombre='Evento corregido').exists())

    def test_rechaza_correo_de_otro_participante(self):
        Participante.objects.create(nombre_completo='Otra persona', email='corregida@example.com')
        respuesta = self.client.post(self.url, self.datos())
        self.assertIn('email', respuesta.context['participante_form'].errors)
        self.comprobar_sin_cambios()

    def test_rechaza_constancia_y_codigo_duplicados(self):
        curso = Curso.objects.create(nombre='Evento corregido')
        Constancia.objects.create(
            participante=self.participante, curso=curso,
            fecha_inicio=date(2026, 10, 1), fecha_termino=date(2026, 10, 3),
            duracion_en_horas=2, firma_gerente=self.gerente,
            firma_especialista=self.gerente, codigo_verificacion='CORREGIDO',
        )
        respuesta = self.client.post(self.url, self.datos())
        self.assertIn('__all__', respuesta.context['constancia_form'].errors)
        self.assertIn('codigo_verificacion', respuesta.context['constancia_form'].errors)
        self.comprobar_sin_cambios()
        self.assertEqual(Constancia.objects.count(), 2)

    def test_reutiliza_curso_y_sincroniza_tipo_webinar(self):
        curso = Curso.objects.create(nombre='Evento corregido')
        for tipo in ('webinar', 'teorica', 'curso'):
            with self.subTest(tipo=tipo):
                respuesta = self.client.post(self.url, self.datos(**{'constancia-tipo': tipo}))
                self.assertEqual(respuesta.status_code, 302)
                self.constancia.refresh_from_db()
                self.assertEqual(self.constancia.es_webinar, tipo != 'curso')
                self.assertEqual(self.constancia.curso_id, curso.pk)
        self.assertEqual(Curso.objects.count(), 2)

    def test_puede_limpiar_fechas_y_vencimiento(self):
        respuesta = self.client.post(self.url, self.datos(**{
            'constancia-fechas_evento': '', 'constancia-fecha_vencimiento': '',
        }))
        self.assertEqual(respuesta.status_code, 302)
        self.constancia.refresh_from_db()
        self.assertEqual(self.constancia.fechas_evento, [])
        self.assertEqual(self.constancia.fecha_texto, '3 de octubre de 2026')
        self.assertIsNone(self.constancia.fecha_vencimiento)

    def test_conflicto_al_guardar_revierte_participante_y_curso(self):
        with patch.object(Constancia, 'save', side_effect=IntegrityError('conflicto')):
            respuesta = self.client.post(self.url, self.datos())
        self.assertContains(respuesta, 'No se guardaron los cambios.')
        self.comprobar_sin_cambios()
        self.assertFalse(Curso.objects.filter(nombre='Evento corregido').exists())

    def test_constancia_inexistente_devuelve_404(self):
        self.assertEqual(self.client.get(reverse('users:editar_constancia', args=[99999])).status_code, 404)


def libro_prueba(dias='8, 9, 10', mes='septiembre', explicitas=True, filas_fechas=None, fecha_texto=None):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = '8 sep'
    hoja.append(['Nombre de la capacitación:', 'Curso de prueba'])
    hoja.append(['Modalidad', 'Presencial'])
    hoja.append(['Duración', '12 h'])
    if fecha_texto is not None:
        hoja.append(['Fecha:', fecha_texto])
    elif explicitas:
        hoja.append(['Fecha:', 'dia', 'mes', 'año '])
        for valores in (filas_fechas if filas_fechas is not None else [(dias, mes, 2026)]):
            hoja.append([None, *valores])
    hoja.append([])
    hoja.append(['Nombre', 'Correo', 'Calificación'])
    hoja.append(['Persona Aprobada', 'aprobada@example.com', 95])
    hoja.append(['Persona Reprobada', 'reprobada@example.com', 60])
    salida = BytesIO()
    libro.save(salida)
    libro.close()
    return salida.getvalue()


class FechasExcelTests(SimpleTestCase):
    def test_fecha_completa_en_celda_de_texto(self):
        for texto in (
            '13,14 y 15 de septiembre del 2026',
            '13 14 15 de septiembre de 2026',
            '13, 14, 15 de septiembre 2026',
            '13,14 y 15 de septiembre',
        ):
            with self.subTest(texto=texto):
                sesion, = analizar_libro(libro_prueba(fecha_texto=texto), anio=2026)
                self.assertEqual(sesion['fechas'], [date(2026, 9, d) for d in (13, 14, 15)])

    def test_texto_con_fecha_invalida_no_se_trunca(self):
        with self.assertRaisesRegex(ValueError, 'fecha inexistente'):
            analizar_libro(libro_prueba(fecha_texto='30 y 31 de septiembre del 2026'))

    def test_texto_con_uno_dos_o_mas_dias(self):
        for dias in [(13,), (13, 15), (13, 14, 15, 16, 17)]:
            texto = ', '.join(str(d) for d in dias) + ' de septiembre del 2026'
            self.assertEqual(leer_fechas_texto(texto), [date(2026, 9, d) for d in dias])

    def test_lee_todas_las_filas_de_fechas(self):
        sesion, = analizar_libro(libro_prueba(filas_fechas=[
            (12, 'septiembre', 2016),
            (13, 'septiembre', 2016),
            (14, 'septiembre', 2016),
        ]))
        self.assertEqual(sesion['fechas'], [date(2016, 9, d) for d in (12, 13, 14)])

    def test_filas_con_mes_y_anio_compartidos(self):
        sesion, = analizar_libro(libro_prueba(filas_fechas=[
            (8, 'septiembre', 2026), (10, None, None), (11, None, None), (14, None, None),
        ]))
        self.assertEqual(formatear_fechas(sesion['fechas']), '8, 10, 11 y 14 de septiembre de 2026')

    def test_fecha_invalida_en_segunda_fila_se_rechaza(self):
        with self.assertRaisesRegex(ValueError, 'fecha inexistente'):
            analizar_libro(libro_prueba(filas_fechas=[
                (30, 'septiembre', 2026), (31, 'septiembre', 2026),
            ]))

    def test_filas_de_fechas_cruzan_mes_y_anio(self):
        sesion, = analizar_libro(libro_prueba(filas_fechas=[
            (31, 'diciembre', 2026), (2, 'enero', 2027),
        ]))
        self.assertEqual(sesion['fechas'], [date(2026, 12, 31), date(2027, 1, 2)])

    def test_importacion_conserva_dias_calificaciones_y_horas(self):
        sesion, = analizar_libro(libro_prueba(), anio=2025)
        self.assertEqual(sesion['fechas'], [date(2026, 9, d) for d in (8, 9, 10)])
        self.assertEqual(sesion['fecha'], date(2026, 9, 8))
        self.assertEqual(sesion['duracion_horas'], 12)
        self.assertEqual((sesion['aprobados'], sesion['reprobados']), (1, 1))

    def test_no_agrega_dias_intermedios_y_quita_repetidos(self):
        sesion, = analizar_libro(libro_prueba(dias='10; 8 y 10'))
        self.assertEqual(formatear_fechas(sesion['fechas']), '8 y 10 de septiembre de 2026')

    def test_dia_unico_numerico(self):
        fechas = leer_fechas_excel([['Día', 'Mes', 'Año'], [8.0, 9.0, 2026.0]])
        self.assertEqual(formatear_fechas(fechas), '8 de septiembre de 2026')

    def test_fechas_invalidas_no_se_sustituyen_por_nombre_de_hoja(self):
        for dias, mes in [('31', 'septiembre'), ('8-10', 'septiembre'), ('', 'septiembre'), ('8', 'desconocido')]:
            with self.subTest(dias=dias, mes=mes):
                with self.assertRaisesRegex(ValueError, 'Hoja "8 sep"'):
                    analizar_libro(libro_prueba(dias=dias, mes=mes))

    def test_formato_anterior_sin_columnas_de_fecha(self):
        sesion, = analizar_libro(libro_prueba(explicitas=False), anio=2026)
        self.assertEqual(sesion['fechas'], [date(2026, 9, 8)])

    def test_formato_con_cambio_de_anio(self):
        self.assertEqual(
            formatear_fechas(['2027-01-02', '2026-12-31']),
            '31 de diciembre de 2026 y 2 de enero de 2027',
        )


class ConstanciasCalificacionTests(TestCase):
    def setUp(self):
        self.evaluador = Evaluador.objects.create_user(
            username='especialista', first_name='Firma', last_name='Prueba', es_gerente=True
        )
        self.client.force_login(self.evaluador)

    def subir(self, contenido):
        return self.client.post(reverse('users:libro_paso1'), {
            'archivo': SimpleUploadedFile('prueba.xlsx', contenido),
            'anio': 2026,
            'calificacion_minima': 80,
            'firma_especialista': self.evaluador.pk,
        })

    def test_frase_con_tres_fechas_llega_completa_al_pdf(self):
        self.subir(libro_prueba(fecha_texto='13,14 y 15 de septiembre del 2026'))
        fechas = ['2026-09-13', '2026-09-14', '2026-09-15']
        self.assertEqual(self.client.session['libro_sesiones'][0]['fechas'], fechas)
        self.assertContains(
            self.client.get(reverse('users:libro_paso2')),
            '13, 14 y 15 de septiembre de 2026',
        )
        self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        constancia = Constancia.objects.get()
        self.assertEqual(constancia.fechas_evento, fechas)
        self.assertEqual(constancia.fecha_inicio, date(2026, 9, 13))
        self.assertEqual(constancia.fecha_termino, date(2026, 9, 15))
        pdf = PdfReader(BytesIO(_generar_pdf_bytes(constancia)))
        self.assertEqual(len(pdf.pages), 1)
        texto = ' '.join(pdf.pages[0].extract_text().split())
        self.assertIn(
            'Realizado el 13, 14 y 15 de septiembre de 2026 en la Ciudad de México', texto
        )

    def test_flujo_completo_y_pdf_con_tres_dias(self):
        respuesta = self.subir(libro_prueba())
        self.assertRedirects(respuesta, reverse('users:libro_paso2'))
        sesion, = self.client.session['libro_sesiones']
        self.assertEqual(sesion['fechas'], ['2026-09-08', '2026-09-09', '2026-09-10'])
        self.assertContains(self.client.get(reverse('users:libro_paso2')), '8, 9 y 10 de septiembre de 2026')
        respuesta = self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        self.assertEqual(respuesta.status_code, 302)
        constancia = Constancia.objects.get()
        self.assertEqual(constancia.fecha_inicio, date(2026, 9, 8))
        self.assertEqual(constancia.fecha_termino, date(2026, 9, 10))
        self.assertEqual(constancia.fechas_evento, sesion['fechas'])
        self.assertEqual(constancia.participante.email, 'aprobada@example.com')
        pdf = PdfReader(BytesIO(_generar_pdf_bytes(constancia)))
        self.assertEqual(len(pdf.pages), 1)
        texto = ' '.join(pdf.pages[0].extract_text().split())
        self.assertIn('Realizado el 8, 9 y 10 de septiembre de 2026 en la Ciudad de México', texto)
        self.assertIn('12 horas', texto)
        # Volver a subir el mismo evento conserva la prevención de duplicados.
        self.subir(libro_prueba())
        self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        self.assertEqual(Constancia.objects.count(), 1)
        # Las constancias anteriores, sin lista de días, conservan su fecha.
        constancia.fechas_evento = []
        pdf = PdfReader(BytesIO(_generar_pdf_bytes(constancia)))
        self.assertIn('10 de septiembre de 2026', pdf.pages[0].extract_text())

    def test_error_de_fecha_visible_al_subir(self):
        respuesta = self.subir(libro_prueba(dias='31'))
        self.assertRedirects(respuesta, reverse('users:libro_paso1'))
        self.assertNotIn('libro_sesiones', self.client.session)
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertTrue(any('fecha inexistente' in m for m in mensajes))

    def test_recargar_excel_completa_fechas_sin_duplicar_constancia(self):
        self.subir(libro_prueba(dias=8))
        self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        constancia = Constancia.objects.get()
        constancia.fechas_evento = []
        constancia.save(update_fields=['fechas_evento'])
        codigo = constancia.codigo_verificacion
        self.subir(libro_prueba())
        respuesta = self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        self.assertEqual(Constancia.objects.count(), 1)
        constancia.refresh_from_db()
        self.assertEqual(constancia.codigo_verificacion, codigo)
        self.assertEqual(constancia.fecha_termino, date(2026, 9, 10))
        self.assertEqual(constancia.fechas_evento, ['2026-09-08', '2026-09-09', '2026-09-10'])
        mensajes = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertTrue(any('Se actualizaron las fechas de 1' in m for m in mensajes))
        html = render_to_string('pdf/constancia_template.html', {'constancia': constancia})
        self.assertIn('8, 9 y 10 de septiembre de 2026', html)

    def test_pdf_de_envio_masivo_incluye_los_dias_exactos(self):
        self.subir(libro_prueba(dias='8 y 10'))
        self.client.post(reverse('users:libro_paso2'), {'hojas': ['8 sep']})
        constancia = Constancia.objects.get()
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            respuesta = self.client.post(reverse('users:enviar_masivo'), {
                'constancias_seleccionadas': [constancia.pk],
            })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        pdf = PdfReader(BytesIO(mail.outbox[0].attachments[0][1]))
        self.assertEqual(len(pdf.pages), 1)
        texto = ' '.join(pdf.pages[0].extract_text().split())
        self.assertIn('Realizado el 8 y 10 de septiembre de 2026 en la Ciudad de México', texto)
        self.assertIn('12 horas', texto)
