# Generated by Django 3.1.5 on 2022-04-18 16:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("elasticHal", "0002_auto_20220418_1750"),
    ]

    operations = [
        migrations.AddField(
            model_name="elastichal",
            name="name",
            field=models.CharField(default="", max_length=50),
        ),
    ]
