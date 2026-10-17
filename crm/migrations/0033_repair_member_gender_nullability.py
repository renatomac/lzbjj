"""Repair legacy MySQL Member.gender NOT NULL schema drift.

The Django model already permits null/blank; this migration only repairs
databases where the physical column still rejects NULL.
"""
from django.db import migrations


def allow_unknown_gender(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return
    Member = apps.get_model("crm", "Member")
    table = Member._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT IS_NULLABLE FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = %s AND COLUMN_NAME = 'gender'""",
            [table],
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Member.gender column is missing")
        if row[0] == "NO":
            quoted_table = connection.ops.quote_name(table)
            cursor.execute(
                f"ALTER TABLE {quoted_table} MODIFY COLUMN gender varchar(20) NULL"
            )


class Migration(migrations.Migration):
    dependencies = [("crm", "0032_biometric_consent_verification_withdrawal")]
    operations = [migrations.RunPython(allow_unknown_gender, migrations.RunPython.noop)]
