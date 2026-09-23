from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0003_backfill_tipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='constancia',
            name='fechas_evento',
            field=models.JSONField(
                default=list, blank=True, verbose_name='Días de la capacitación'
            ),
        ),
    ]
