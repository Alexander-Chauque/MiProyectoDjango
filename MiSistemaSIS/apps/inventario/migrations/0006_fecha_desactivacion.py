# Guarda cuándo se desactivó cada plato, bebida e ingrediente.
# Un trigger de MySQL completa la fecha solo, venga el cambio de Django, la API
# o phpMyAdmin. Con esa fecha se permite eliminar recién a los 2 meses.

from django.db import migrations, models

# (modelo, columna del estado)
TABLAS = [
    ("Plato", "estado_plato"),
    ("Bebida", "disponible_bebida"),
    ("Ingrediente", "estado_ingrediente"),
]


def _nombre_trigger(tabla, momento):
    return f"trg_{tabla}_fecha_desactivacion_{momento}"


def crear_triggers(apps, schema_editor):
    # Solo MySQL: en las pruebas (SQLite) la fecha la completa el modelo al guardar
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for modelo, estado in TABLAS:
            tabla = apps.get_model("inventario", modelo)._meta.db_table
            for momento in ("insert", "update"):
                cursor.execute(f"DROP TRIGGER IF EXISTS {_nombre_trigger(tabla, momento)}")

            # Al crearlo ya desactivado, la cuenta empieza en ese momento.
            # UTC_TIMESTAMP(): Django guarda las fechas en UTC (USE_TZ = True).
            cursor.execute(
                f"""
                CREATE TRIGGER {_nombre_trigger(tabla, "insert")}
                BEFORE INSERT ON {tabla}
                FOR EACH ROW
                BEGIN
                    IF NEW.{estado} = 0 THEN
                        SET NEW.fecha_desactivacion = UTC_TIMESTAMP();
                    ELSE
                        SET NEW.fecha_desactivacion = NULL;
                    END IF;
                END
                """
            )
            # Al desactivarlo se anota la fecha; al reactivarlo se borra (la cuenta vuelve a cero).
            # Si el estado no cambia, se conserva la fecha que ya tenía, aunque el programa mande otra.
            cursor.execute(
                f"""
                CREATE TRIGGER {_nombre_trigger(tabla, "update")}
                BEFORE UPDATE ON {tabla}
                FOR EACH ROW
                BEGIN
                    IF NEW.{estado} = OLD.{estado} THEN
                        SET NEW.fecha_desactivacion = OLD.fecha_desactivacion;
                    ELSEIF NEW.{estado} = 0 THEN
                        SET NEW.fecha_desactivacion = UTC_TIMESTAMP();
                    ELSE
                        SET NEW.fecha_desactivacion = NULL;
                    END IF;
                END
                """
            )


def borrar_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for modelo, _ in TABLAS:
            tabla = apps.get_model("inventario", modelo)._meta.db_table
            for momento in ("insert", "update"):
                cursor.execute(f"DROP TRIGGER IF EXISTS {_nombre_trigger(tabla, momento)}")


def fechar_los_ya_desactivados(apps, schema_editor):
    """Los que ya estaban desactivados no tienen fecha: la cuenta de 2 meses empieza hoy."""
    from django.utils import timezone

    ahora = timezone.now()
    for modelo, estado in TABLAS:
        apps.get_model("inventario", modelo).objects.filter(**{estado: False, "fecha_desactivacion__isnull": True}).update(
            fecha_desactivacion=ahora
        )


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0005_imagen_ingrediente'),
    ]

    operations = [
        migrations.AddField(
            model_name='bebida',
            name='fecha_desactivacion',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='ingrediente',
            name='fecha_desactivacion',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='plato',
            name='fecha_desactivacion',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        # Primero las fechas de los que ya estaban desactivados, después los triggers
        # (el trigger de UPDATE conservaría la fecha vieja, que es NULL).
        migrations.RunPython(fechar_los_ya_desactivados, migrations.RunPython.noop),
        migrations.RunPython(crear_triggers, borrar_triggers),
    ]
