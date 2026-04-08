from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("greenhouses", "0002_update_content_types"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="nantesgreenhouses",
            table="greenhouses_nantesgreenhouses",
        ),
        migrations.AlterModelTable(
            name="greenhouse",
            table="greenhouses_greenhouse",
        ),
        migrations.AlterModelTable(
            name="culture",
            table="greenhouses_culture",
        ),
        migrations.AlterModelTable(
            name="greenhousegrowthcycle",
            table="greenhouses_greenhousegrowthcycle",
        ),
        migrations.AlterModelTable(
            name="growthtimestepset",
            table="greenhouses_growthtimestepset",
        ),
        migrations.AlterModelTable(
            name="growthshare",
            table="greenhouses_growthshare",
        ),
        migrations.AlterModelTable(
            name="casestudybaseobjects",
            table="greenhouses_casestudybaseobjects",
        ),
    ]
