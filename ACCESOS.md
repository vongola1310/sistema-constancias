# Administración de accesos a constancias

El dashboard incluye **Accesos de usuarios** para cuentas administradoras
(`is_superuser=True`). Permite buscar por nombre, usuario o correo, filtrar por
estado, recorrer páginas y guardar el acceso de cada cuenta.

- **Cuenta activa:** habilita el inicio de sesión; desactivarla bloquea también
  las siguientes solicitudes de una sesión existente.
- **Crear constancias:** permite los flujos por curso, webinar y calificación.
  Se valida en cada GET y POST, incluidos los segundos pasos de los asistentes.
  Revocarlo conserva la consulta, edición y descarga del historial existente.
- Las cuentas administradoras están protegidas y conservan la creación de
  constancias. Ser firmante gerente (`es_gerente`) o personal (`is_staff`) no
  concede administración de accesos.
- Solo los administradores registran evaluadores desde la aplicación. El alta
  mantiene su sesión y permite autorizar la creación con una casilla; inicia
  desmarcada. El panel no concede roles administrativos ni elimina usuarios.

## Aplicación a una instalación existente

Antes de iniciar la versión actualizada, ejecutar con el entorno de la aplicación:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

La migración `0005_acceso_constancias` agrega un campo y conserva el permiso de
los usuarios activos existentes. Las cuentas nuevas inician sin permiso.
No altera constancias, participantes, firmas ni contraseñas.
Los estáticos incorporan `static/css/accesos.css`; incluirlos mediante el proceso
de despliegue habitual (`collectstatic` si corresponde) y reiniciar el servidor.

## Verificación aislada

```powershell
.\venv\Scripts\python.exe manage.py test users --settings=config.settings_test
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings_test
```

La configuración de pruebas usa SQLite en memoria, almacenamiento en memoria
y correo local. No consulta la base configurada para producción ni envía correos.
