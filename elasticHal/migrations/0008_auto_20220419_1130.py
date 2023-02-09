# Generated by Django 3.1.5 on 2022-04-19 09:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("elasticHal", "0007_auto_20220418_1822"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="laboratory",
            name="name",
        ),
        migrations.AddField(
            model_name="laboratory",
            name="acronym",
            field=models.CharField(default="", max_length=10),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="halStructId",
            field=models.CharField(default="", max_length=20),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="idref",
            field=models.CharField(default="", max_length=20),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="label",
            field=models.CharField(default="", max_length=300),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="rsnr",
            field=models.CharField(default="", max_length=20),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="structSirene",
            field=models.CharField(default="", max_length=10),
        ),
    ]
