# Generated by Django 3.1.5 on 2022-04-19 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elasticHal', '0008_auto_20220419_1130'),
    ]

    operations = [
        migrations.RenameField(
            model_name='laboratory',
            old_name='idref',
            new_name='idRef',
        ),
        migrations.RenameField(
            model_name='structure',
            old_name='name',
            new_name='acronym',
        ),
        migrations.AddField(
            model_name='researcher',
            name='aurehalId',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='firstName',
            field=models.CharField(default='', max_length=30),
        ),
        migrations.AddField(
            model_name='researcher',
            name='function',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='researcher',
            name='halId_s',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='researcher',
            name='idRef',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='lab',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='labHalId',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='lastName',
            field=models.CharField(default='', max_length=30),
        ),
        migrations.AddField(
            model_name='researcher',
            name='ldapId',
            field=models.CharField(default='', max_length=30),
        ),
        migrations.AddField(
            model_name='researcher',
            name='mail',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='researcher',
            name='structDomain',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='structSirene',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='researcher',
            name='supannAffectation',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.AddField(
            model_name='researcher',
            name='supannEntiteAffectationPrincipale',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='researcher',
            name='type',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AddField(
            model_name='structure',
            name='domain',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='structure',
            name='label',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='structure',
            name='structSirene',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='laboratory',
            name='structSirene',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='researcher',
            name='name',
            field=models.CharField(default='', max_length=80),
        ),
    ]