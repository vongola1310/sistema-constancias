# Descarga al terminar las constancias por calificación

Tras seleccionar las sesiones del paso 2 y pulsar **Generar Constancias**, aparece
un resumen de las sesiones y sus fechas exactas con el botón **Descargar
constancias generadas de las fechas seleccionadas**.

El ZIP incluye los PDF de las constancias procesadas en esa selección: nuevas,
existentes y aquellas cuyas fechas se actualizaron. No busca todos los registros
del mismo día ni incluye otras sesiones del Excel. Cada constancia aparece una
sola vez, organizada en carpetas por fecha de inicio y curso, con nombres seguros
y un identificador para evitar archivos repetidos.

La descarga utiliza los datos actuales de cada constancia, igual que el historial.
Puede repetirse y reintentarse sin generar más registros. Si se elimina alguna
constancia o falla un PDF, se informa el problema sin entregar un ZIP incompleto.

Los últimos cinco resultados se conservan en la sesión que los generó. Cada uno
tiene su propio enlace, para que procesar otro archivo no cambie la descarga de
una pestaña anterior. Requieren iniciar sesión; otra sesión o usuario no puede
usar esos enlaces. Al cerrar sesión, las constancias permanecen en el historial.
Revocar la creación conserva la descarga de los resultados existentes, como en
el historial; desactivar la cuenta impide el acceso.

No requiere migraciones ni cambios en datos existentes. Verificación aislada:

```powershell
.\venv\Scripts\python.exe manage.py test users.test_libro_descargas users.tests.ConstanciasCalificacionTests --settings=config.settings_test
```
