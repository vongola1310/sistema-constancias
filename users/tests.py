from datetime import date
from io import BytesIO

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pypdf import PdfReader

from .fechas import formatear_fechas, leer_fechas_excel
from .importadores import analizar_libro
from .models import Constancia, Evaluador
from .views import _generar_pdf_bytes


def libro_prueba(dias='8, 9, 10', mes='septiembre', explicitas=True):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = '8 sep'
    hoja.append(['Nombre de la capacitación:', 'Curso de prueba'])
    hoja.append(['Modalidad', 'Presencial'])
    hoja.append(['Duración', '12 h'])
    if explicitas:
        hoja.append(['Fecha:', 'dia', 'mes', 'año '])
        hoja.append([None, dias, mes, 2026])
    hoja.append([])
    hoja.append(['Nombre', 'Correo', 'Calificación'])
    hoja.append(['Persona Aprobada', 'aprobada@example.com', 95])
    hoja.append(['Persona Reprobada', 'reprobada@example.com', 60])
    salida = BytesIO()
    libro.save(salida)
    libro.close()
    return salida.getvalue()


class FechasExcelTests(SimpleTestCase):
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
