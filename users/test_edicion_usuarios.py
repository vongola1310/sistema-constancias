from unittest.mock import patch

from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from .models import Evaluador


class EdicionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Evaluador.objects.create_superuser('admin-edicion', password='OriginalAdmin7!')
        cls.usuario = Evaluador.objects.create_user(
            'usuario-edicion', password='OriginalUsuario8!', first_name='Ana',
            last_name='López', email='ana@example.com', cargo='Especialista',
            puede_crear_constancias=True, es_gerente=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse('users:editar_usuario', args=[self.usuario.pk])

    def datos(self, cuenta=None, **cambios):
        cuenta = cuenta or self.usuario
        url = reverse('users:editar_usuario', args=[cuenta.pk])
        version = self.client.get(url).context['form']['version'].value()
        datos = {
            'username': cuenta.username, 'first_name': cuenta.first_name,
            'last_name': cuenta.last_name, 'email': cuenta.email, 'cargo': cuenta.cargo,
            'new_password1': '', 'new_password2': '', 'version': version,
        }
        datos.update(cambios)
        return datos

    def test_dashboard_ofrece_edicion_para_usuarios_y_administrador(self):
        respuesta = self.client.get(reverse('users:dashboard'))
        for cuenta in (self.usuario, self.admin):
            self.assertContains(respuesta, reverse('users:editar_usuario', args=[cuenta.pk]))

    def test_formulario_muestra_datos_sin_exponer_credenciales_y_sin_cache(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="usuario-edicion"')
        self.assertContains(respuesta, 'value="Ana"')
        self.assertContains(respuesta, 'Deja ambos campos vacíos')
        self.assertNotContains(respuesta, self.usuario.password)
        self.assertNotContains(respuesta, 'OriginalUsuario8!')
        self.assertIn('no-store', respuesta.headers['Cache-Control'])
        self.assertEqual(respuesta.context['form']['new_password1'].value(), None)

    def test_actualiza_datos_conservando_clave_permisos_y_firma(self):
        clave_original = self.usuario.password
        respuesta = self.client.post(self.url, self.datos(
            username='ana.actualizada', first_name='Ana María', last_name='García',
            email='ana.actualizada@example.com', cargo='Coordinadora',
        ))
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'ana.actualizada')
        self.assertEqual(self.usuario.get_full_name(), 'Ana María García')
        self.assertEqual(self.usuario.email, 'ana.actualizada@example.com')
        self.assertEqual(self.usuario.cargo, 'Coordinadora')
        self.assertEqual(self.usuario.password, clave_original)
        self.assertTrue(self.usuario.es_gerente)
        self.assertTrue(self.usuario.puede_crear_constancias)
        self.assertFalse(self.usuario.is_superuser)
        cliente = Client()
        self.assertFalse(cliente.login(username='usuario-edicion', password='OriginalUsuario8!'))
        self.assertTrue(cliente.login(username='ana.actualizada', password='OriginalUsuario8!'))

    def test_nueva_clave_se_guarda_con_hash_y_revoca_sesiones_del_usuario(self):
        cliente = Client()
        cliente.force_login(self.usuario)
        clave = 'NuevaClaveAzul39!'
        respuesta = self.client.post(self.url, self.datos(new_password1=clave, new_password2=clave))
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(clave))
        self.assertNotEqual(self.usuario.password, clave)
        self.assertFalse(self.usuario.check_password('OriginalUsuario8!'))
        self.assertEqual(cliente.get(reverse('users:dashboard')).status_code, 302)
        self.assertTrue(cliente.login(username=self.usuario.username, password=clave))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.admin.pk))

    def test_administrador_cambia_su_usuario_y_clave_sin_perder_esta_sesion(self):
        otra_sesion = Client()
        otra_sesion.force_login(self.admin)
        clave = 'ClaveAdminRenovada42!'
        url = reverse('users:editar_usuario', args=[self.admin.pk])
        respuesta = self.client.post(url, self.datos(
            self.admin, username='admin-renovado', new_password1=clave, new_password2=clave,
        ), follow=True)
        self.assertContains(respuesta, 'Accesos de usuarios')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.admin.pk))
        self.assertEqual(otra_sesion.get(reverse('users:dashboard')).status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.check_password(clave))

    def test_edita_otra_cuenta_administradora_sin_cambiar_sus_roles(self):
        otro = Evaluador.objects.create_superuser('otro-admin-edicion')
        url = reverse('users:editar_usuario', args=[otro.pk])
        respuesta = self.client.post(url, self.datos(otro, username='otro-admin-renombrado'))
        self.assertEqual(respuesta.status_code, 302)
        otro.refresh_from_db()
        self.assertEqual(otro.username, 'otro-admin-renombrado')
        self.assertTrue(otro.is_superuser)
        self.assertTrue(otro.is_active)

    def test_rechaza_duplicados_incluso_con_distintas_mayusculas(self):
        for nombre in (self.admin.username, self.admin.username.upper()):
            respuesta = self.client.post(self.url, self.datos(username=nombre, first_name='No guardar'))
            self.assertFormError(respuesta.context['form'], 'username', 'Ya existe un usuario con ese nombre, incluso con otras mayúsculas.')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Ana')

    def test_rechaza_usuario_y_correo_invalidos(self):
        for campo, valor in (('username', ''), ('username', 'usuario con espacios'), ('email', 'correo-sin-arroba')):
            respuesta = self.client.post(self.url, self.datos(**{campo: valor}))
            self.assertIn(campo, respuesta.context['form'].errors)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario-edicion')

    def test_validacion_de_clave_no_guarda_otros_datos_ni_reexpone_la_clave(self):
        casos = [
            ('NuevaClaveAzul39!', '', 'new_password2'),
            ('', 'NuevaClaveAzul39!', 'new_password1'),
            ('NuevaClaveAzul39!', 'OtraClaveVerde41!', 'new_password2'),
            ('Ab3!', 'Ab3!', 'new_password1'),
            ('123456789012', '123456789012', 'new_password1'),
            ('password', 'password', 'new_password1'),
            ('A' * 129, 'A' * 129, 'new_password1'),
        ]
        for clave, confirmacion, campo in casos:
            with self.subTest(campo=campo, longitud=len(clave)):
                respuesta = self.client.post(self.url, self.datos(
                    first_name='No guardar', new_password1=clave, new_password2=confirmacion,
                ))
                self.assertIn(campo, respuesta.context['form'].errors)
                if clave:
                    self.assertNotContains(respuesta, f'value="{clave}"')
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.first_name, 'Ana')
                self.assertTrue(self.usuario.check_password('OriginalUsuario8!'))

    def test_valida_similitud_con_el_nombre_de_usuario_editado(self):
        respuesta = self.client.post(self.url, self.datos(
            username='ClaveIgualAlUsuario', new_password1='ClaveIgualAlUsuario',
            new_password2='ClaveIgualAlUsuario',
        ))
        self.assertIn('new_password1', respuesta.context['form'].errors)

    def test_rechaza_edicion_anonima_o_sin_privilegios(self):
        datos = self.datos(first_name='No guardar')
        self.client.logout()
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(self.url, datos).status_code, 302)
        self.usuario.is_staff = True
        self.usuario.save()
        self.client.force_login(self.usuario)
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(self.url, datos).status_code, 403)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Ana')

    def test_no_permite_modificar_roles_permisos_ni_hash_por_post(self):
        self.client.post(self.url, self.datos(
            is_superuser='on', is_staff='on', is_active='', es_gerente='',
            puede_crear_constancias='', password='un-hash-inyectado',
        ))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(self.usuario.is_staff)
        self.assertTrue(self.usuario.is_active)
        self.assertTrue(self.usuario.es_gerente)
        self.assertTrue(self.usuario.puede_crear_constancias)
        self.assertTrue(self.usuario.check_password('OriginalUsuario8!'))

    def test_requiere_csrf_y_usuario_existente(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(self.url, self.datos()).status_code, 403)
        self.assertEqual(self.client.get(reverse('users:editar_usuario', args=[999999])).status_code, 404)
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_detecta_formulario_desactualizado_y_version_faltante(self):
        datos = self.datos(first_name='No guardar')
        Evaluador.objects.filter(pk=self.usuario.pk).update(cargo='Cambio simultáneo')
        respuesta = self.client.post(self.url, datos)
        self.assertContains(respuesta, 'Esta cuenta cambió')
        datos.pop('version')
        respuesta = self.client.post(self.url, datos)
        self.assertIn('version', respuesta.context['form'].errors)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Ana')
        self.assertEqual(self.usuario.cargo, 'Cambio simultáneo')

    def test_conflicto_de_base_no_cambia_datos_ni_clave(self):
        datos = self.datos(username='otro-usuario', new_password1='NuevaClaveAzul39!', new_password2='NuevaClaveAzul39!')
        with patch.object(Evaluador, 'save', side_effect=IntegrityError('duplicate username')):
            respuesta = self.client.post(self.url, datos)
        self.assertIn('username', respuesta.context['form'].errors)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario-edicion')
        self.assertTrue(self.usuario.check_password('OriginalUsuario8!'))

    def test_conserva_busqueda_y_pagina_al_volver(self):
        respuesta = self.client.post(
            self.url + '?acceso_q=Ana&acceso_estado=autorizados&acceso_pagina=2', self.datos(),
        )
        self.assertEqual(respuesta.url, '/dashboard/?acceso_q=Ana&acceso_estado=autorizados&acceso_pagina=2#accesos')
