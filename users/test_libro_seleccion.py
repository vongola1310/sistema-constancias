from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Constancia, Evaluador, Participante
from .test_libro_descargas import libro_descarga


class SeleccionAlumnosLibroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.evaluador = Evaluador.objects.create_user(
            'seleccion-alumnos', es_gerente=True, puede_crear_constancias=True,
        )

    def setUp(self):
        self.client.force_login(self.evaluador)
        self.url = reverse('users:libro_paso2')

    def subir(self, dos_sesiones=False):
        hojas = [('Primera', 'Curso primero', '8 y 10')]
        if dos_sesiones:
            hojas.append(('Segunda', 'Curso segundo', '15'))
        libro = openpyxl.load_workbook(BytesIO(libro_descarga(hojas)))
        for hoja in libro:
            hoja.append(['Carla Aprobada', 'carla@example.com', 90])
            hoja.append(['Sin Correo', None, 95])
        archivo = BytesIO()
        libro.save(archivo)
        libro.close()
        respuesta = self.client.post(reverse('users:libro_paso1'), {
            'archivo': SimpleUploadedFile('alumnos.xlsx', archivo.getvalue()),
            'anio': 2026, 'calificacion_minima': 80, 'firma_especialista': self.evaluador.pk,
        })
        self.assertRedirects(respuesta, self.url)
        self.vista = self.client.get(self.url)

    def alumno(self, correo, hoja='Primera'):
        sesion = next(s for s in self.vista.context['sesiones'] if s['hoja'] == hoja)
        return next(p['seleccion_id'] for p in sesion['personas'] if p['email'] == correo)

    def datos(self, alumnos, hojas=None):
        return {'seleccion_token': self.vista.context['seleccion_token'],
                'hojas': hojas or ['Primera'], 'alumnos': alumnos}

    def resultado(self, datos):
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)
        pagina = self.client.get(respuesta.url)
        self.assertEqual(pagina.status_code, 200)
        self.assertIsNotNone(pagina.context['resultado'])
        return pagina

    def test_vista_tiene_casillas_y_solo_habilita_aprobados_con_correo(self):
        self.subir()
        self.assertContains(self.vista, 'Ver y seleccionar alumnos')
        self.assertContains(self.vista, 'Deseleccionar todos')
        personas = self.vista.context['sesiones'][0]['personas']
        self.assertEqual({p['email'] for p in personas if p['habilitado']}, {'ana@example.com', 'carla@example.com'})
        self.assertTrue(all(p['seleccionado'] for p in personas if p['habilitado']))
        self.assertContains(self.vista, 'name="alumnos"', count=2)

    def test_generar_un_solo_alumno_limita_tambien_el_zip(self):
        self.subir()
        resultado = self.resultado(self.datos([self.alumno('carla@example.com')]))
        self.assertEqual(Constancia.objects.count(), 1)
        constancia = Constancia.objects.get()
        self.assertEqual(constancia.participante.email, 'carla@example.com')
        self.assertFalse(Participante.objects.filter(email='ana@example.com').exists())
        self.assertEqual(resultado.context['resultado']['total'], 1)
        descarga = reverse('users:descargar_libro_resultado', args=[resultado.context['lote_id']])
        with patch('users.views._generar_pdf_bytes', return_value=b'%PDF-prueba') as generar_pdf:
            respuesta = self.client.get(descarga)
            paquete = b''.join(respuesta.streaming_content)
            respuesta.close()
        with ZipFile(BytesIO(paquete)) as zip_file:
            self.assertEqual(len(zip_file.namelist()), 1)
            self.assertIn('carla-aprobada', zip_file.namelist()[0])
        self.assertEqual(generar_pdf.call_args.args[0].pk, constancia.pk)

    def test_puede_seleccionar_todos_los_aprobados(self):
        self.subir()
        self.resultado(self.datos([self.alumno('ana@example.com'), self.alumno('carla@example.com')]))
        self.assertEqual(Constancia.objects.count(), 2)

    def test_envio_compacto_del_navegador_genera_solo_el_alumno_elegido(self):
        self.subir()
        datos = self.datos([])
        datos.pop('alumnos')
        datos['alumnos_json'] = json.dumps([self.alumno('carla@example.com')])
        self.resultado(datos)
        self.assertEqual(Constancia.objects.get().participante.email, 'carla@example.com')

    def test_envio_compacto_vacio_o_malformado_no_genera_todos(self):
        self.subir()
        for contenido in ('[]', 'null', '{}', '[1]', 'invalido'):
            datos = self.datos([self.alumno('ana@example.com')])
            datos['alumnos_json'] = contenido
            self.client.post(self.url, datos)
            self.assertFalse(Constancia.objects.exists())

    def test_deseleccionar_todos_no_genera_ni_actualiza(self):
        self.subir()
        respuesta = self.client.post(self.url, self.datos([]), follow=True)
        self.assertContains(respuesta, 'Selecciona al menos un alumno')
        self.assertFalse(Constancia.objects.exists())
        self.assertFalse(Participante.objects.exists())
        self.assertFalse(any(p['seleccionado'] for p in respuesta.context['sesiones'][0]['personas']))
        datos = self.datos([])
        datos.pop('alumnos')
        self.client.post(self.url, datos)
        self.assertFalse(Constancia.objects.exists())

    def test_seleccion_independiente_por_sesion_y_sesion_vacia_omitida(self):
        self.subir(dos_sesiones=True)
        resultado = self.resultado(self.datos(
            [self.alumno('carla@example.com', 'Segunda')], ['Primera', 'Segunda'],
        ))
        constancia = Constancia.objects.get()
        self.assertEqual(constancia.curso.nombre, 'Curso segundo')
        self.assertEqual(constancia.participante.email, 'carla@example.com')
        self.assertEqual(len(resultado.context['resultado']['sesiones']), 1)

    def test_ignora_alumnos_de_sesiones_no_marcadas(self):
        self.subir(dos_sesiones=True)
        self.resultado(self.datos([
            self.alumno('carla@example.com'), self.alumno('ana@example.com', 'Segunda'),
        ]))
        self.assertEqual(Constancia.objects.count(), 1)
        self.assertEqual(Constancia.objects.get().curso.nombre, 'Curso primero')

    def test_rechaza_alumno_reprobado_o_fila_inexistente(self):
        self.subir()
        for identificador in (self.alumno('beto@example.com'), '999:999'):
            respuesta = self.client.post(self.url, self.datos([
                self.alumno('carla@example.com'), identificador,
            ]), follow=True)
            self.assertContains(respuesta, 'alumnos no disponibles')
            self.assertFalse(Constancia.objects.exists())

    def test_no_acepta_seleccion_de_una_vista_previa_anterior(self):
        self.subir()
        anterior = self.datos([self.alumno('ana@example.com')])
        self.subir(dos_sesiones=True)
        respuesta = self.client.post(self.url, anterior, follow=True)
        self.assertContains(respuesta, 'La vista previa cambió')
        self.assertFalse(Constancia.objects.exists())
        anterior.pop('seleccion_token')
        self.client.post(self.url, anterior)
        self.assertFalse(Constancia.objects.exists())

    def test_fallo_de_guardado_conserva_exactamente_los_alumnos_elegidos(self):
        self.subir()
        carla = self.alumno('carla@example.com')
        with patch.object(Constancia, 'save', side_effect=IntegrityError('fallo simulado')):
            respuesta = self.client.post(self.url, self.datos([carla]), follow=True)
        self.assertFalse(Constancia.objects.exists())
        self.assertTrue(respuesta.context['sesiones'][0]['marcada'])
        marcados = [p['seleccion_id'] for p in respuesta.context['sesiones'][0]['personas'] if p['seleccionado']]
        self.assertEqual(marcados, [carla])
        self.resultado(self.datos([carla]))
        self.assertEqual(Constancia.objects.get().participante.email, 'carla@example.com')

    def test_reimportar_un_alumno_no_incluye_constancias_de_los_deseleccionados(self):
        self.subir()
        self.resultado(self.datos([self.alumno('ana@example.com'), self.alumno('carla@example.com')]))
        ana = Constancia.objects.get(participante__email='ana@example.com')
        ana.fechas_evento = ['2026-09-08']
        ana.save(update_fields=['fechas_evento'])
        self.subir()
        resultado = self.resultado(self.datos([self.alumno('carla@example.com')]))
        self.assertEqual(Constancia.objects.count(), 2)
        self.assertNotIn(ana.pk, resultado.context['resultado']['constancia_ids'])
        ana.refresh_from_db()
        self.assertEqual(ana.fechas_evento, ['2026-09-08'])
