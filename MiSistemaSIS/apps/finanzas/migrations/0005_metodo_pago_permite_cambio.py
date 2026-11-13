from django.db import migrations, models


def marcar_efectivo(apps, schema_editor):
    """El efectivo es el único método cargado con el que se da vuelto."""
    MetodoPago = apps.get_model("finanzas", "metodo_pago")
    MetodoPago.objects.filter(nombre_metodo_pago__iexact="Efectivo").update(permite_cambio=True)


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0004_auto_20261027_0211"),
    ]

    operations = [
        migrations.AddField(
            model_name="metodo_pago",
            name="permite_cambio",
            field=models.BooleanField(default=False, verbose_name="Permite dar vuelto"),
        ),
        migrations.RunPython(marcar_efectivo, migrations.RunPython.noop),
    ]
