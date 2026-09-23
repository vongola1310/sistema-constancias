from datetime import date
from io import BytesIO

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.core import mail
from django.urls import reverse
from pypdf import PdfReader

from .fechas import formatear_fechas, leer_fechas_excel, leer_fechas_texto
from .importadores import analizar_libro
from .models import Constancia, Evaluador
from .views import _generar_pdf_bytes


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
