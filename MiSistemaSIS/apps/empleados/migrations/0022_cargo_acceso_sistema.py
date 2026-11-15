from django.db import migrations, models

# Cargos que pueden ingresar al sistema. El nivel 5 (administrador) siempre puede,
# para que nunca quede nadie que pueda administrarlo.
CARGOS_CON_ACCESO = ["Mozo", "Administrador"]


def habilitar_mozo_y_administrador(apps, schema_editor):
    Cargo = apps.get_model("empleados", "Cargo")
    for cargo in Cargo.objects.all():
        if cargo.nombre_cargo.lower() in {n.lower() for n in CARGOS_CON_ACCESO} or cargo.nivel_acceso >= 5:
            cargo.acceso_sistema = True
            cargo.save(update_fields=["acceso_sistema"])


class Migration(migrations.Migration):

    dependencies = [
        ("empleados", "0021_alter_cargo_id_cargo"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargo",
            name="acceso_sistema",
            field=models.BooleanField(default=False, verbose_name="Puede ingresar al sistema"),
        ),
        migrations.RunPython(habilitar_mozo_y_administrador, migrations.RunPython.noop),
    ]
