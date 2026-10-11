"""
Migration to convert notifications_notification table to utf8mb4 encoding.

This allows emoji and other multi-byte UTF-8 characters to be stored properly.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward migration: Convert whichever notifications table is present to utf8mb4.
            # This handles both the default app table name and the custom crm_notifications label.
            """
            SET @table_name := (
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME IN ('notifications_notification', 'crm_notifications_notification')
                ORDER BY CASE TABLE_NAME WHEN 'notifications_notification' THEN 1 ELSE 2 END
                LIMIT 1
            );

            SET @sql := CONCAT(
                'ALTER TABLE `', @table_name, '` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
            );
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;

            SET @sql := CONCAT(
                'ALTER TABLE `', @table_name, '` MODIFY message VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
            );
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            """,
            # Reverse migration (shouldn't need to run, but included for completeness)
            migrations.RunSQL.noop,
        ),
    ]
