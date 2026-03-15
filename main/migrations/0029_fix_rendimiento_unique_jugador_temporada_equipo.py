from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0028_profile_pic_flat_folder'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='rendimientohistoricojugador',
            unique_together={('jugador', 'temporada', 'equipo')},
        ),
    ]
