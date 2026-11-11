from datetime import date
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from pypdf import PdfReader

from .libro_descargas import MAX_RESULTADOS, RESULTADOS_SESSION_KEY
from .models import Constancia, Curso, Evaluador, Participante


def libro_descarga(hojas=None):
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for hoja, curso, dias in hojas or [('Septiembre', 'Curso seleccionado', '8 y 10')]:
        ws = libro.create_sheet(hoja)
        for fila in [
            ['Nombre de la capacitación:', curso], ['Modalidad', 'Presencial'],
            ['Duración', '12 h'], ['Fecha:', 'dia', 'mes', 'año'],
            [None, dias, 'septiembre', 2026], [], ['Nombre', 'Correo', 'Calificación'],
            ['Ana Aprobada', 'ana@example.com', 95], ['Beto Reprobado', 'beto@example.com', 60],
        ]:
            ws.append(fila)
    salida = BytesIO()
    libro.save(salida)
    libro.close()
    return salida.getvalue()


class LibroDescargasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.evaluador = Evaluador.objects.create_user(
            username='evaluador-descargas', first_name='Firma', last_name='Prueba',
            es_gerente=True, puede_crear_constancias=True,
        )

    def setUp(self):
        self.client.force_login(self.evaluador)

    def subir(self, hojas=None):
        respuesta = self.client.post(reverse('users:libro_paso1'), {
            'archivo': SimpleUploadedFile('sesiones.xlsx', libro_descarga(hojas)),
            'anio': 2026, 'calificacion_minima': 80, 'firma_especialista': self.evaluador.pk,
        })
        self.assertRedirects(respuesta, reverse('users:libro_paso2'))

    def seleccion(self, elegidas):
        vista = self.client.get(reverse('users:libro_paso2'))
        return {
            'hojas': elegidas, 'seleccion_token': vista.context['seleccion_token'],
            'alumnos': [p['seleccion_id'] for s in vista.context['sesiones']
                        if s['hoja'] in elegidas for p in s['personas'] if p['habilitado']],
        }

    def generar(self, elegidas=None):
        respuesta = self.client.post(reverse('users:libro_paso2'), self.seleccion(elegidas or ['Septiembre']))
        self.assertEqual(respuesta.status_code, 302)
        resultado = self.client.get(respuesta.url)
        self.assertEqual(resultado.status_code, 200)
        return resultado, reverse('users:descargar_libro_resultado', args=[resultado.context['lote_id']])

    def abrir_zip(self, url, cliente=None):
        respuesta = (cliente or self.client).get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.headers['Content-Type'], 'application/zip')
        self.assertIn('attachment;', respuesta.headers['Content-Disposition'])
        self.assertIn('no-store', respuesta.headers['Cache-Control'])
        contenido = b''.join(respuesta.streaming_content)
        respuesta.close()
        return ZipFile(BytesIO(contenido))

    def test_flujo_real_muestra_boton_fechas_exactas_y_pdf_en_zip(self):
        self.subir()
        resultado, descarga = self.generar()
        self.assertContains(resultado, 'Descargar constancias generadas de las fechas seleccionadas')
        self.assertContains(resultado, '8 y 10 de septiembre de 2026')
        self.assertEqual(resultado.context['resultado']['nuevas'], 1)
        self.assertNotIn('libro_sesiones', self.client.session)
        self.assertNotIn('libro_config', self.client.session)
        with self.abrir_zip(descarga) as paquete:
            self.assertEqual(len(paquete.namelist()), 1)
            nombre = paquete.namelist()[0]
            self.assertTrue(nombre.startswith('2026-09-08_curso-seleccionado_'))
            pdf = PdfReader(BytesIO(paquete.read(nombre)))
            texto = ' '.join(pdf.pages[0].extract_text().split())
            self.assertIn('Ana Aprobada', texto)
            self.assertIn('8 y 10 de septiembre de 2026', texto)
            self.assertNotIn('Beto Reprobado', texto)

    def test_solo_descarga_seleccion_sin_otros_registros_del_mismo_dia(self):
        self.subir([
            ('Seleccionada', 'Curso seleccionado', '8 y 10'),
            ('Otra fecha', 'Curso seleccionado', '15'),
            ('Otro curso', 'Curso excluido', '8 y 10'),
        ])
        curso = Curso.objects.create(nombre='Curso seleccionado')
        persona = Participante.objects.create(nombre_completo='Fuera del Excel', email='fuera@example.com')
        ajena = Constancia.objects.create(
            participante=persona, curso=curso, fecha_inicio=date(2026, 9, 8), fecha_termino=date(2026, 9, 10),
            duracion_en_horas=12, firma_gerente=self.evaluador, firma_especialista=self.evaluador,
            codigo_verificacion='FUERA-EXCEL', tipo='teorica',
        )
        resultado, descarga = self.generar(['Seleccionada'])
        ids = resultado.context['resultado']['constancia_ids']
        self.assertNotIn(ajena.pk, ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(resultado.context['resultado']['sesiones']), 1)
        with patch('users.views._generar_pdf_bytes', side_effect=lambda c: f'%PDF-{c.pk}'.encode()) as pdf:
            with self.abrir_zip(descarga + f'?constancia_ids={ajena.pk}') as paquete:
                self.assertEqual(len(paquete.namelist()), 1)
                self.assertEqual(paquete.read(paquete.namelist()[0]), f'%PDF-{ids[0]}'.encode())
            self.assertEqual(pdf.call_args.args[0].pk, ids[0])

    def test_seleccion_multiple_y_descargas_repetidas_no_crean_registros(self):
        self.subir([('Primera', 'Curso uno', '8'), ('Segunda', 'Curso dos', '11 y 14')])
        resultado, descarga = self.generar(['Primera', 'Segunda'])
        self.assertEqual(resultado.context['resultado']['total'], 2)
        self.assertContains(resultado, '11 y 14 de septiembre de 2026')
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba'):
            for _ in range(2):
                with self.abrir_zip(descarga) as paquete:
                    self.assertEqual(len(paquete.namelist()), 2)
                    self.assertEqual(len({n.split('/')[0] for n in paquete.namelist()}), 2)
        self.assertEqual(self.client.get(resultado.request['PATH_INFO']).status_code, 200)
        self.assertEqual(Constancia.objects.count(), 2)

    def test_reimportacion_incluye_existentes_y_fechas_actualizadas(self):
        self.subir([('Septiembre', 'Curso seleccionado', '8')])
        self.generar()
        constancia = Constancia.objects.get()
        self.subir()
        resultado, descarga = self.generar()
        self.assertEqual(resultado.context['resultado']['nuevas'], 0)
        self.assertEqual(resultado.context['resultado']['actualizadas'], 1)
        constancia.refresh_from_db()
        self.assertEqual(constancia.fechas_evento, ['2026-09-08', '2026-09-10'])
        self.subir()
        resultado, descarga = self.generar()
        self.assertEqual(resultado.context['resultado']['existentes'], 1)
        self.assertEqual(resultado.context['resultado']['constancia_ids'], [constancia.pk])
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba'):
            with self.abrir_zip(descarga) as paquete:
                self.assertEqual(len(paquete.namelist()), 1)
        self.assertEqual(Constancia.objects.count(), 1)

    def test_no_duplica_archivos_si_el_libro_repite_la_misma_sesion(self):
        self.subir([('Original', 'Curso repetido', '8'), ('Copia', 'Curso repetido', '8')])
        resultado, descarga = self.generar(['Original', 'Copia'])
        self.assertEqual(resultado.context['resultado']['total'], 1)
        self.assertEqual(resultado.context['resultado']['nuevas'], 1)
        self.assertEqual(resultado.context['resultado']['existentes'], 0)
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba'):
            with self.abrir_zip(descarga) as paquete:
                self.assertEqual(len(paquete.namelist()), 1)

    def test_una_generacion_nueva_no_sustituye_el_zip_anterior(self):
        self.subir()
        primero, descargar_primero = self.generar()
        self.subir([('Septiembre', 'Curso distinto', '15')])
        segundo, descargar_segundo = self.generar()
        self.assertNotEqual(descargar_primero, descargar_segundo)
        with patch('users.views._generar_pdf_bytes', side_effect=lambda c: f'%PDF-{c.pk}'.encode()):
            for resultado, descarga in ((primero, descargar_primero), (segundo, descargar_segundo)):
                with self.abrir_zip(descarga) as paquete:
                    self.assertEqual(paquete.read(paquete.namelist()[0]), f'%PDF-{resultado.context["resultado"]["constancia_ids"][0]}'.encode())

    def test_otro_usuario_o_sesion_no_pueden_usar_el_enlace(self):
        self.subir()
        resultado, descarga = self.generar()
        url_resultado = resultado.request['PATH_INFO']
        otro = Client()
        for url in (descarga, url_resultado):
            self.assertEqual(otro.get(url).status_code, 302)
        otro.force_login(Evaluador.objects.create_user('otro-evaluador'))
        for url in (descarga, url_resultado):
            self.assertEqual(otro.get(url).status_code, 404)
        otro.force_login(self.evaluador)
        self.assertEqual(otro.get(descarga).status_code, 404)
        self.assertEqual(self.client.post(descarga).status_code, 405)

    def test_resultado_inexistente_muestra_salida_clara(self):
        for ruta in ('libro_resultado', 'descargar_libro_resultado'):
            respuesta = self.client.get(reverse('users:' + ruta, args=[uuid4()]))
            self.assertContains(respuesta, 'Resumen no disponible', status_code=404)

    def test_fallo_de_pdf_no_entrega_zip_parcial_y_permite_reintento(self):
        self.subir()
        resultado, descarga = self.generar()
        for fallo in (None, RuntimeError('Fallo simulado')):
            opciones = {'side_effect': fallo} if isinstance(fallo, Exception) else {'return_value': None}
            with patch('users.views._generar_pdf_bytes', **opciones), self.assertLogs('users.libro_descargas', level='ERROR'):
                respuesta = self.client.get(descarga)
            self.assertContains(respuesta, 'Las constancias siguen guardadas', status_code=500)
            self.assertContains(respuesta, 'Descargar constancias generadas', status_code=500)
            self.assertFalse(respuesta.streaming)
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-recuperado'):
            with self.abrir_zip(descarga) as paquete:
                self.assertEqual(len(paquete.namelist()), 1)
        self.assertEqual(Constancia.objects.count(), 1)

    def test_constancia_eliminada_se_informa_sin_zip_incompleto(self):
        self.subir([('Primera', 'Curso uno', '8'), ('Segunda', 'Curso dos', '15')])
        _, descarga = self.generar(['Primera', 'Segunda'])
        Constancia.objects.first().delete()
        with patch('users.views._generar_pdf_bytes') as pdf:
            respuesta = self.client.get(descarga)
            pdf.assert_not_called()
        self.assertContains(respuesta, 'ya no está disponible', status_code=410)

    def test_nombres_del_zip_son_seguros_y_diferentes(self):
        self.subir([('Primera', '../../Curso / especial', '8')])
        _, descarga = self.generar(['Primera'])
        Participante.objects.update(nombre_completo='../Ana\\Prueba')
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba'):
            with self.abrir_zip(descarga) as paquete:
                nombre = paquete.namelist()[0]
                self.assertEqual(nombre.count('/'), 1)
                self.assertNotIn('..', nombre)
                self.assertNotIn('\\', nombre)
                self.assertTrue(nombre.endswith(f'_{Constancia.objects.get().pk}.pdf'))

    def test_revocar_creacion_conserva_descarga_y_desactivar_bloquea(self):
        self.subir()
        _, descarga = self.generar()
        Evaluador.objects.filter(pk=self.evaluador.pk).update(puede_crear_constancias=False)
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba'):
            with self.abrir_zip(descarga) as paquete:
                self.assertEqual(len(paquete.namelist()), 1)
        Evaluador.objects.filter(pk=self.evaluador.pk).update(is_active=False)
        self.assertEqual(self.client.get(descarga).status_code, 302)

    def test_fallo_al_guardar_no_publica_resultado_y_revierte_datos(self):
        self.subir()
        seleccion = self.seleccion(['Septiembre'])
        with patch.object(Constancia, 'save', side_effect=IntegrityError('Error simulado')):
            respuesta = self.client.post(reverse('users:libro_paso2'), seleccion)
        self.assertRedirects(respuesta, reverse('users:libro_paso2'))
        self.assertFalse(Constancia.objects.exists())
        self.assertFalse(self.client.session.get(RESULTADOS_SESSION_KEY))
        self.assertIn('libro_sesiones', self.client.session)

    def test_seleccion_vacia_o_desconocida_conserva_el_paso_2(self):
        self.subir()
        for hojas in ([], ['No existe']):
            respuesta = self.client.post(reverse('users:libro_paso2'), self.seleccion(hojas))
            self.assertRedirects(respuesta, reverse('users:libro_paso2'))
        self.assertFalse(Constancia.objects.exists())
        self.assertFalse(self.client.session.get(RESULTADOS_SESSION_KEY))

    def test_conserva_solo_los_ultimos_cinco_resultados(self):
        enlaces = []
        for _ in range(MAX_RESULTADOS + 1):
            self.subir()
            resultado, descarga = self.generar()
            enlaces.append(resultado.request['PATH_INFO'])
        self.assertEqual(len(self.client.session[RESULTADOS_SESSION_KEY]), MAX_RESULTADOS)
        self.assertEqual(self.client.get(enlaces[0]).status_code, 404)
        self.assertEqual(self.client.get(enlaces[-1]).status_code, 200)
