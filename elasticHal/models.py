from django.db import models

# Create your models here.


class Structure(models.Model):
    """
    Définition du modèle Structure dans Django
    """
    structSirene = models.CharField(max_length=20, default="")
    label = models.CharField(max_length=50, default="")
    acronym = models.CharField(max_length=50, default="")
    domain = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.structSirene


class Laboratory(models.Model):
    """
    Définition du modèle Laboratory dans Django
    """
    class Meta:
        verbose_name_plural = "Laboratories"
    structSirene = models.CharField(max_length=20, default="")
    acronym = models.CharField(max_length=10, default="")
    label = models.CharField(max_length=300, default="")
    halStructId = models.CharField(max_length=20, default="")
    rsnr = models.CharField(max_length=20, default="")
    idRef = models.CharField(max_length=20, default="")

    def __str__(self):
        return self.idRef


class Researcher(models.Model):
    """
    Définition du modèle Researcher dans Django
    """
    structSirene = models.CharField(max_length=20, default="")
    ldapId = models.CharField(max_length=30, default="")
    name = models.CharField(max_length=80, default="")
    type = models.CharField(max_length=20, default="")
    function = models.CharField(max_length=50, default="")
    mail = models.CharField(max_length=50, default="")
    lab = models.CharField(max_length=20, default="")
    supannAffectation = models.CharField(max_length=100, default="")
    supannEntiteAffectationPrincipale = models.CharField(max_length=50, default="")
    halId_s = models.CharField(max_length=50, default="")
    labHalId = models.CharField(max_length=20, default="")
    idRef = models.CharField(max_length=20, default="")
    structDomain = models.CharField(max_length=20, default="")
    firstName = models.CharField(max_length=30, default="")
    lastName = models.CharField(max_length=30, default="")
    aurehalId = models.CharField(max_length=20, default="")

    def __str__(self):
        return self.ldapId
