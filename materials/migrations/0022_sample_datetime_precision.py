from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0021_sample_time_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="sample",
            name="datetime_precision",
            field=models.CharField(
                blank=True,
                choices=[("year", "Year"), ("date", "Date"), ("time", "Date and time")],
                default="",
                help_text="Known sampling date precision, interpreted in the default timezone. Blank preserves legacy behavior: midnight is displayed as a date.",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="sample",
            name="datetime",
            field=models.DateTimeField(
                blank=True,
                help_text="When the sample was taken, with its known precision recorded separately.",
                null=True,
                verbose_name="sampling date/time",
            ),
        ),
    ]
