from django.db import models

# Create your models here.


class Structure(models.Model):
    """
    Model for the structure of the institution in Django database
    :param structSirene: Sirene number of the structure
    param label: name of the structure
    param acronym: acronym of the structure
    param domain: web domain of the structure
    :return:
    """
    structSirene = models.CharField(max_length=20, default="")
    label = models.CharField(max_length=50, default="")
    acronym = models.CharField(max_length=50, default="")
    domain = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.structSirene


class Laboratory(models.Model):
    """
    Model for the laboratory in Django database
    structSirene: Sirene number of the affiliated structure
    acronym: acronym of the laboratory
    label: name of the laboratory
    halStructId: HAL id of the laboratory
    rsnr: RSNR id of the laboratory
    idRef: idRef of the laboratory
    :return:
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
    Model for the researcher in Django database
    structSirene: Sirene number of the affiliated structure
    ldapId: LDAP id of the researcher
    name: full name of the researcher
    type: category of the researcher (student, professor, etc.)
    function: function of the researcher (research, teaching, etc.)
    mail: mail of the researcher
    lab: acronym of the laboratory of the researcher
    supannAffectation: affiliation of the researcher in the university
    supannEntiteAffectationPrincipale: affiliation of the researcher in the university
    halId_s: HAL id of the researcher
    labHalId: HAL id of the laboratory of the researcher
    idRef: idRef of the researcher
    structDomain: web domain of the structure of the researcher
    firstName: first name of the researcher
    lastName: last name of the researcher
    aurehalId: aurehalId of the researcher
    :return:
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
