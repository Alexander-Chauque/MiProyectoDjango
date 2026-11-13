from django.db import migrations

# Umbrales de las reglas de alerta. Se editan desde el admin (tabla configuracion), no en el código.
VALORES = [
    ("desvio_venta_inusual", "3", "Venta inusual: cantidad de desvíos estándar sobre la media."),
    ("minutos_comanda_demorada", "30", "Comanda demorada: minutos en pendiente o en preparación."),
    ("horas_caja_abierta", "12", "Caja abierta: horas sin cerrarse."),
    ("enviar_correo_alertas", "1", "1 = las alertas nuevas también se envían por correo; 0 = solo bandeja."),
]


def cargar(apps, schema_editor):
    Configuracion = apps.get_model("notificaciones", "Configuracion")
    for clave, valor, descripcion in VALORES:
        # No pisa valores que el usuario ya haya cambiado
        Configuracion.objects.get_or_create(
            clave_configuracion=clave,
            defaults={"valor_configuracion": valor, "descripcion_configuracion": descripcion},
        )


class Migration(migrations.Migration):
    dependencies = [("notificaciones", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
