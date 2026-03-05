import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("bd_models", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_claimed", models.DateField()),
                ("player", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="daily_claim",
                    to="bd_models.player",
                )),
            ],
            options={
                "db_table": "dailyclaim",
                "managed": True,
            },
        ),
    ]
