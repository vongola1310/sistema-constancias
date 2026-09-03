from django.db import migrations


def poner_tipo(apps, schema_editor):
    Constancia = apps.get_model('users', 'Constancia')
    Constancia.objects.filter(es_webinar=True).update(tipo='webinar')
    Constancia.objects.filter(es_webinar=False).update(tipo='curso')


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_constancia_tipo'),
    ]

    operations = [
        migrations.RunPython(poner_tipo, revertir),
    ]