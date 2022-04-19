from django.db import models

# Create your models here.


class Structure(models.Model):
    name = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.name


class Laboratory(models.Model):
    class Meta:
        verbose_name_plural = "Laboratories"
    structSirene = models.CharField(max_length=10, default="")
    acronym = models.CharField(max_length=10, default="")
    label = models.CharField(max_length=300, default="")
    halStructId = models.CharField(max_length=20, default="")
    rsnr = models.CharField(max_length=20, default="")
    idref = models.CharField(max_length=20, default="")

    def __str__(self):
        return self.acronym


class Researcher(models.Model):
    name = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.name

