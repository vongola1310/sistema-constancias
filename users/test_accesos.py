from django.contrib.auth.models import Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .models import Constancia, Curso, Evaluador, Participante


class AccesosTests(TestCase):
    rutas_creacion = ('crear_lote', 'webinar_paso1', 'webinar_paso2', 'libro_paso1', 'libro_paso2')

    @classmethod
    def setUpTestData(cls):
        cls.admin = Evaluador.objects.create_superuser('administrador', password='PruebaSegura7!')
        cls.usuario = Evaluador.objects.create_user(
            'evaluador', first_name='María', last_name='López', email='evaluador@example.com',
            password='PruebaSegura7!', es_gerente=True,
        )
        cls.autorizado = Evaluador.objects.create_user('autorizado', puede_crear_constancias=True)
        cls.inactivo = Evaluador.objects.create_user('inactivo', is_active=False, puede_crear_constancias=True)

    def setUp(self):
        self.url = reverse('users:actualizar_acceso', args=[self.usuario.pk])

    def test_panel_exclusivo_de_superusuarios(self):
        for usuario in (self.usuario, self.autorizado):
            self.client.force_login(usuario)
            respuesta = self.client.get(reverse('users:dashboard'))
            self.assertNotContains(respuesta, 'id="accesos"')
            self.assertNotContains(respuesta, reverse('users:crear_evaluador'))
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('users:dashboard'))
        self.assertContains(respuesta, 'Accesos de usuarios')
        self.assertContains(respuesta, 'Cuenta administradora protegida')
        self.assertNotContains(respuesta, self.usuario.password)
        self.assertEqual(respuesta.context['accesos_resumen'], {
            'total': 4, 'autorizados': 2, 'sin_permiso': 1, 'inactivos': 1,
        })

    def test_busqueda_filtros_y_paginacion(self):
        self.client.force_login(self.admin)
        url = reverse('users:dashboard')
        respuesta = self.client.get(url, {'acceso_q': 'María López', 'acceso_estado': 'sin_permiso'})
        self.assertEqual([u.pk for u in respuesta.context['accesos_pagina']], [self.usuario.pk])
        respuesta = self.client.get(url, {'acceso_estado': 'inactivos'})
        self.assertEqual([u.pk for u in respuesta.context['accesos_pagina']], [self.inactivo.pk])
        Evaluador.objects.bulk_create([Evaluador(username=f'usuario-{n}') for n in range(12)])
        respuesta = self.client.get(url, {'acceso_pagina': '2'})
        self.assertEqual(len(respuesta.context['accesos_pagina']), 6)
        respuesta = self.client.get(url, {'acceso_q': 'sin coincidencias', 'acceso_pagina': 'inválida'})
        self.assertContains(respuesta, 'No se encontraron usuarios')

    def test_anonimo_no_puede_crear_ni_administrar(self):
        for ruta in self.rutas_creacion + ('crear_evaluador',):
            url = reverse('users:' + ruta)
            for metodo in (self.client.get, self.client.post):
                respuesta = metodo(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('users:login'), respuesta.url)
        self.assertEqual(self.client.post(self.url).status_code, 302)

    def test_usuario_sin_permiso_no_puede_abrir_ni_enviar_los_cinco_pasos(self):
        self.client.force_login(self.usuario)
        for ruta in self.rutas_creacion:
            for metodo in (self.client.get, self.client.post):
                with self.subTest(ruta=ruta, metodo=metodo.__name__):
                    self.assertEqual(metodo(reverse('users:' + ruta)).status_code, 403)
        self.assertFalse(Constancia.objects.exists())

    def test_oculta_creacion_y_conserva_historial(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse('users:dashboard'))
        self.assertContains(respuesta, 'Creación de constancias sin permiso')
        for ruta in ('crear_lote', 'webinar_paso1', 'libro_paso1'):
            self.assertNotContains(respuesta, f'href="{reverse("users:" + ruta)}"')
        self.assertEqual(self.client.get(reverse('users:historial_constancias')).status_code, 200)

    def test_habilitar_y_revocar_aplica_a_una_sesion_abierta(self):
        sesion_usuario = Client()
        sesion_usuario.force_login(self.usuario)
        self.client.force_login(self.admin)
        self.client.post(self.url, {'is_active': 'on', 'puede_crear_constancias': 'on', 'estado_anterior': '1:0'})
        self.assertEqual(sesion_usuario.get(reverse('users:crear_lote')).status_code, 200)
        sesion = sesion_usuario.session
        sesion['webinar_event_data'] = {'curso_nombre': 'Pendiente'}
        sesion['libro_sesiones'] = [{'hoja': 'Pendiente'}]
        sesion.save()
        self.client.post(self.url, {'is_active': 'on', 'estado_anterior': '1:1'})
        for ruta in self.rutas_creacion:
            self.assertEqual(sesion_usuario.post(reverse('users:' + ruta)).status_code, 403)
        self.assertFalse(Constancia.objects.exists())

    def test_desactivar_invalida_la_sesion_y_reactivar_restaura_login(self):
        sesion_usuario = Client()
        sesion_usuario.force_login(self.usuario)
        self.client.force_login(self.admin)
        self.client.post(self.url, {'estado_anterior': '1:0'})
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertEqual(sesion_usuario.get(reverse('users:dashboard')).status_code, 302)
        self.assertFalse(sesion_usuario.login(username='evaluador', password='PruebaSegura7!'))
        self.client.post(self.url, {'is_active': 'on', 'estado_anterior': '0:0'})
        self.assertTrue(sesion_usuario.login(username='evaluador', password='PruebaSegura7!'))

    def test_no_permite_escalar_privilegios_por_campos_adicionales(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'is_active': 'on', 'estado_anterior': '1:0', 'is_superuser': 'on', 'is_staff': 'on'})
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(self.usuario.is_staff)

    def test_cuentas_administradoras_protegidas(self):
        otro = Evaluador.objects.create_superuser('otro-admin')
        self.client.force_login(self.admin)
        for usuario in (self.admin, otro):
            respuesta = self.client.post(reverse('users:actualizar_acceso', args=[usuario.pk]), {'estado_anterior': '1:0'})
            self.assertEqual(respuesta.status_code, 403)
            usuario.refresh_from_db()
            self.assertTrue(usuario.is_active)

    def test_firmante_gerente_y_staff_no_pueden_administrar(self):
        self.usuario.is_staff = True
        self.usuario.save()
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(self.url, {'is_active': 'on', 'puede_crear_constancias': 'on', 'estado_anterior': '1:0'}).status_code, 403)
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(reverse('users:crear_evaluador')).status_code, 403)

    def test_rechaza_get_formulario_incompleto_y_usuario_inexistente(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.post(self.url, {'is_active': 'on', 'puede_crear_constancias': 'on'})
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.puede_crear_constancias)
        self.assertEqual(self.client.post(reverse('users:actualizar_acceso', args=[999999])).status_code, 404)

    def test_no_sobrescribe_cambios_de_otro_administrador(self):
        self.client.force_login(self.admin)
        Evaluador.objects.filter(pk=self.usuario.pk).update(puede_crear_constancias=True)
        respuesta = self.client.post(self.url, {'estado_anterior': '1:0'}, follow=True)
        self.assertContains(respuesta, 'Otro administrador modificó este acceso')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.assertTrue(self.usuario.puede_crear_constancias)

    def test_cambios_requieren_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(self.url, {'estado_anterior': '1:0'}).status_code, 403)

    def test_nuevo_usuario_sin_permiso_por_defecto_y_sesion_admin_preservada(self):
        self.client.force_login(self.admin)
        datos = {'username': 'nuevo', 'password1': 'ClaveDistinta8!$', 'password2': 'ClaveDistinta8!$'}
        respuesta = self.client.post(reverse('users:crear_evaluador'), datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.admin.pk))
        self.assertFalse(Evaluador.objects.get(username='nuevo').puede_crear_constancias)
        datos.update(username='nuevo-habilitado', puede_crear_constancias='on')
        self.client.post(reverse('users:crear_evaluador'), datos)
        self.assertTrue(Evaluador.objects.get(username='nuevo-habilitado').puede_crear_constancias)

    def test_autorizado_crea_constancia_de_curso(self):
        curso = Curso.objects.create(nombre='Curso autorizado')
        participante = Participante.objects.create(nombre_completo='Participante', email='participante@example.com')
        self.client.force_login(self.autorizado)
        respuesta = self.client.post(reverse('users:crear_lote'), {
            'curso': curso.pk, 'participantes': [participante.pk],
            'fecha_inicio': '2026-11-01', 'fecha_termino': '2026-11-02',
            'duracion_en_horas': '8', 'firma_especialista': self.autorizado.pk,
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Constancia.objects.count(), 1)

    def test_superusuario_conserva_creacion_sin_bandera(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.admin.puede_crear_constancias)
        for ruta in ('crear_lote', 'webinar_paso1', 'libro_paso1'):
            self.assertEqual(self.client.get(reverse('users:' + ruta)).status_code, 200)

    def test_django_admin_no_elude_permiso_de_creacion(self):
        self.usuario.is_staff = True
        self.usuario.save()
        self.usuario.user_permissions.add(Permission.objects.get(content_type__app_label='users', codename='add_constancia'))
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('admin:users_constancia_add')).status_code, 403)


class MigracionAccesosTests(TransactionTestCase):
    def test_preserva_activos_y_nuevas_cuentas_inician_sin_permiso(self):
        executor = MigrationExecutor(connection)
        anterior = [('users', '0004_constancia_fechas_evento')]
        actual = [('users', '0005_acceso_constancias')]
        executor.migrate(anterior)
        try:
            UsuarioAnterior = executor.loader.project_state(anterior).apps.get_model('users', 'Evaluador')
            activo = UsuarioAnterior.objects.create(username='existente-activo', is_active=True)
            inactivo = UsuarioAnterior.objects.create(username='existente-inactivo', is_active=False)
            executor = MigrationExecutor(connection)
            executor.migrate(actual)
            UsuarioActual = executor.loader.project_state(actual).apps.get_model('users', 'Evaluador')
            self.assertTrue(UsuarioActual.objects.get(pk=activo.pk).puede_crear_constancias)
            self.assertFalse(UsuarioActual.objects.get(pk=inactivo.pk).puede_crear_constancias)
            self.assertFalse(UsuarioActual.objects.create(username='nuevo').puede_crear_constancias)
        finally:
            MigrationExecutor(connection).migrate(actual)
