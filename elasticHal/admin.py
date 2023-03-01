import csv

# Celery-progress
# from celery_progress.backend import ProgressRecorder
from django.contrib import admin, messages

# from django.contrib.auth.models import Group, User
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from elasticHal.collect_from_HAL import (
    collect_laboratories_data2,
    collect_researchers_data2,
)

from .forms import CsvImportForm, ExportToElasticForm, PopulateLab
from .insert_entities import create_index
from .models import Laboratory, Structure
from .views import get_index_list

# Celery
# from celery import shared_task


admin.site.site_header = "Administration de SoVisu"


# Celery tasks
# task_id1 = task_id2 = task_id3 = None


class ExportCsv:
    def export_as_csv(self, request, queryset):
        """
        Exporte les données sélectionnées dans un fichier CSV
        """
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={meta}.csv"
        response.write("\ufeff".encode())

        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response

    export_as_csv.short_description = "Exporter les éléments sélectionnés"


class ElasticActions:
    """
    Actions pour l'index Elasticsearch
    """

    @staticmethod
    # @shared_task(bind=True)
    def export_to_elastic(request):
        """
        Initialise la création des index Elasticsearch à partir des csv enregistrés
        """
        taches = []
        if request.method == "POST":
            form = ExportToElasticForm(request.POST)
            if form.is_valid():
                structure = form.cleaned_data["Structures"]
                laboratoires = form.cleaned_data["Laboratoires"]

                result1 = create_index.delay(
                    structure=structure,
                    laboratories=laboratoires,
                    django_enabler=True,
                )

                taches.append([0, result1.task_id])

            if len(taches) > 0:
                return render(
                    request,
                    "admin/elasticHal/export_to_elastic.html",
                    context={"form": form, "taches": taches},
                )
            else:
                form = ExportToElasticForm()
                return render(request, "admin/elasticHal/export_to_elastic.html", {"form": form})
        else:
            # Get form instance
            form = ExportToElasticForm()
            # Return
            return render(request, "admin/elasticHal/export_to_elastic.html", {"form": form})

    @staticmethod
    def update_elastic(request):
        """
        Met à jour les données dans les index Elasticsearch sélectionnées
        """
        if request.method == "POST":
            form = PopulateLab(request.POST)
            # structure = request.POST.get('Structures')
            # laboratoires = request.POST.get('Laboratoires')
            # chercheurs = request.POST.get('Chercheurs')
            #  laboratoires =
            # print(f"structure: {structure}," +
            # f"laboratoires: {laboratoires}, chercheurs: {chercheurs}")
            taches = []
            if form.is_valid():
                if "chercheurs" in request.POST.keys():
                    chercheurs = True
                else:
                    chercheurs = False
                if "collectionLabo" in request.POST.keys():
                    collectionLabo = True
                else:
                    collectionLabo = False
                collection = form.cleaned_data["f_index"]
                # print('uuuu ', collection)
                indexes = get_index_list()
                structures = []
                for ind, lab in enumerate(indexes):
                    structures.append(lab[0].split("-")[0])
                structures = list(set(structures))
                if "TOUT" in request.POST.keys():
                    dejaVus = []
                    for ind, lab in enumerate(indexes):
                        laboratoire = lab[0].split("-")[1]
                        structure = lab[0].split("-")[0]
                        if laboratoire not in dejaVus:
                            result1 = collect_laboratories_data2.delay(
                                laboratoire
                            )  # on ferait pas la collecte deux fois pour les labs partagés ?
                            dejaVus.append(laboratoire)
                        else:
                            result1.task_id = None
                        result2 = collect_researchers_data2.delay(struct=structure, idx=lab[0])
                        taches.append(
                            [ind, result1.task_id, result2.task_id]
                        )  # numero; tacheLab, TacheChercheurs

                elif collectionLabo is True:
                    if collection == "":  # comme si c'était "TOUT"
                        dejaVus = []
                        for ind, lab in enumerate(indexes):
                            laboratoire = lab[0].split("-")[1]
                            structure = lab[0].split("-")[0]
                            if laboratoire not in dejaVus:
                                result1 = collect_laboratories_data2.delay(
                                    laboratoire
                                )  # on ferait pas la collecte deux fois pour les labs partagés ?
                                dejaVus.append(laboratoire)
                            else:
                                result1.task_id = None  #
                            result2 = collect_researchers_data2.delay(struct=structure, idx=lab[0])
                            taches.append([ind, result1.task_id, result2.task_id])
                    elif chercheurs is True:
                        laboratoire = collection.split("-")[1]
                        structure = collection.split("-")[0]
                        result1 = collect_laboratories_data2.delay(laboratoire, True)
                        result2 = collect_researchers_data2.delay(struct=structure, idx=collection)
                        taches.append([0, result1.task_id, result2.task_id])
                    else:
                        result1 = collect_laboratories_data2.delay(collectionLabo, True)
                        taches.append([0, result1.task_id, None])
                elif chercheurs is True:  # boucle sur les structures
                    taches = []

                    for ind, struct in enumerate(structures):
                        result2 = collect_researchers_data2.delay(struct=struct, idx="")
                        taches.append([ind, None, result2.task_id])  # numero;  TacheChercheurs
                else:
                    pass  # on devrait pas être là
            else:
                pass  # pas sûr
            if len(taches) > 0:
                # print(taches)
                return render(
                    request,
                    "admin/elasticHal/export_to_elasticLabs2.html",
                    context={"form": form, "taches": taches},
                )
            else:
                return render(
                    request,
                    "admin/elasticHal/export_to_elasticLabs2.html",
                    context={"form": form},
                )
        else:
            form = PopulateLab()

        data = {"form": form}
        return render(request, "admin/elasticHal/export_to_elasticLabs2.html", data)


# Models are under that line
class StructureAdmin(admin.ModelAdmin, ExportCsv):
    """
    Modèle de l'administration des structures
    """

    list_display = ("structSirene", "acronym", "label")
    actions = ["export_as_csv"]

    def get_urls(self):
        """
        Initialise les urls du modèle StructureAdmin
        """
        urls = super().get_urls()
        new_urls = [
            path("upload-csv/", self.upload_csv),
            path("update_elastic/", ElasticActions.update_elastic),
            path("export-elastic/", ElasticActions.export_to_elastic),
        ]
        return new_urls + urls

    @staticmethod
    def upload_csv(request):
        """
        Permet de charger un fichier CSV dans la base de données du modèle Structure
        """
        if request.method == "POST":
            csv_file = request.FILES["importer_un_fichier"]

            if not csv_file.name.endswith(".csv"):
                messages.warning(request, "Le fichier importé n'est pas un .csv")
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # sépare le fichier par ligne

            csv_data.pop(0)  # supprime l'en-tête du csv

            csv_data = list(
                map(str.strip, csv_data)
            )  # enlève les caractères spéciaux afin d'avoir le contenu exact des lignes

            csv_data = list(filter(None, csv_data))  # supprime les lignes vides dans le fichier.

            for line in csv_data:
                fields = line.split(";")
                Structure.objects.update_or_create(
                    structSirene=fields[0],
                    label=fields[1],
                    acronym=fields[2],
                    domain=fields[3],
                )
                # print(created)
            url = reverse("admin:index")
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


class LaboratoryAdmin(admin.ModelAdmin, ExportCsv):
    """
    Modèle de l'administration des laboratoires
    """

    list_display = ("acronym", "label", "halStructId", "idRef", "structSirene")
    list_filter = ("structSirene",)
    actions = ["export_as_csv"]

    def get_urls(self):
        """
        Initialise les urls du modèle LaboratoryAdmin
        """
        urls = super().get_urls()
        new_urls = [
            path("upload-csv/", self.upload_csv),
            path("update_elastic/", ElasticActions.update_elastic),
            path("export-elastic/", ElasticActions.export_to_elastic),
        ]
        return new_urls + urls

    @staticmethod
    def upload_csv(request):
        """
        Permet de charger un fichier CSV dans la base de données du modèle Laboratory
        """
        if request.method == "POST":
            csv_file = request.FILES["importer_un_fichier"]

            if not csv_file.name.endswith(".csv"):
                messages.warning(request, "Le fichier importé n'est pas un .csv")
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # sépare le fichier par ligne

            csv_data.pop(0)  # supprime l'en-tête du csv

            csv_data = list(
                map(str.strip, csv_data)
            )  # enlève les caractères spéciaux afin d'avoir le contenu exact des lignes

            csv_data = list(filter(None, csv_data))  # supprime les lignes vides dans le fichier.

            for x in csv_data:
                fields = x.split(";")  # sépare les lignes en champs
                Laboratory.objects.update_or_create(
                    structSirene=fields[0],
                    acronym=fields[1],
                    label=fields[2],
                    halStructId=fields[3],
                    rsnr=fields[4],
                    idRef=fields[5],
                )
                # print(created)
            url = reverse("admin:index")
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


# Unregister the default admin site
# admin.site.unregister(User)
# admin.site.unregister(Group)


# Register your models here.
admin.site.register(Structure, StructureAdmin)
admin.site.register(Laboratory, LaboratoryAdmin)
