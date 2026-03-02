# Generated migration to remove HistorialEquiposJugador and cleanup columns

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0023_add_prediccion_jugador'),
    ]

    operations = [
        # Remove HistorialEquiposJugador model entirely (cascade deletes ok since we use EquipoJugadorTemporada)
        migrations.DeleteModel(
            name='HistorialEquiposJugador',
        ),
        # Remove goles_en_propia_puerta_total from RendimientoHistoricoJugador (all zeros, unused)
        migrations.RemoveField(
            model_name='rendimientohistoricojugador',
            name='goles_en_propia_puerta_total',
        ),
    ]
