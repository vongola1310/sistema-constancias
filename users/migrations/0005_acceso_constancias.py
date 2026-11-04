from django.db import migrations, models


def conservar_accesos_existentes(apps, schema_editor):
    Evaluador = apps.get_model('users', 'Evaluador')
    Evaluador.objects.using(schema_editor.connection.alias).filter(
        is_active=True,
    ).update(puede_crear_constancias=True)


class Migration(migrations.Migration):
    dependencies = [('users', '0004_constancia_fechas_evento')]

    operations = [
        migrations.AddField(
            model_name='evaluador',
            name='puede_crear_constancias',
            field=models.BooleanField(
                default=False,
                verbose_name='Puede crear constancias',
                help_text='Permite generar constancias de cursos, webinars y capacitaciones por calificación.',
            ),
        ),
        migrations.RunPython(conservar_accesos_existentes, migrations.RunPython.noop),
    ]
