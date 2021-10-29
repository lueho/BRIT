# Generated by Django 3.2.8 on 2021-10-29 06:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventories', '0010_runningtask'),
    ]

    operations = [
        migrations.RunSQL("""
                INSERT INTO inventories_runningtask (
                    scenario_id,
                    algorithm_id,
                    uuid
                )
                SELECT
                    scenario_id,
                    algorithm_id,
                    uuid
                FROM
                    scenario_evaluator_runningtask;
                
                SELECT setval(pg_get_serial_sequence('"inventories_runningtask"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "inventories_runningtask";
            """, reverse_sql="""
                INSERT INTO scenario_evaluator_runningtask (
                    scenario_id,
                    algorithm_id,
                    uuid
                )
                SELECT
                    scenario_id,
                    algorithm_id,
                    uuid
                FROM
                    inventories_runningtask;
                    
                SELECT setval(pg_get_serial_sequence('"scenario_evaluator_runningtask"','id'), coalesce(max("id"), 1), max("id") IS NOT null) FROM "scenario_evaluator_runningtask";
            """)
    ]