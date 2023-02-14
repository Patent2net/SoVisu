from __future__ import absolute_import, unicode_literals
import csv
from django.contrib import admin, messages
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse

from .models import Structure, Laboratory, Researcher
from django.contrib.auth.models import User, Group

from .insert_entities import create_index
from .collect_from_HAL import (
    collect_data,
    collect_laboratories_data2,
    collect_researchers_data2,
)

from .forms import PopulateLab, ExportToElasticForm, CsvImportForm
from .views import get_index_list

# Celery
from celery import shared_task

# Celery-progress
from celery_progress.backend import ProgressRecorder

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
        response["Content-Disposition"] = "attachment; filename={}.csv".format(meta)
        response.write("\ufeff".encode("utf8"))

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
    def export_to_elastic(request):
        """
        Initialise la création des index Elasticsearch et collecte les données correspondantes via l'API HAL
        """

        if request.method == "POST":
            form = ExportToElasticForm(request.POST)
            if form.is_valid():
                structure = form.cleaned_data["Structures"]
                laboratoires = form.cleaned_data["Laboratoires"]
                chercheurs = form.cleaned_data["Chercheurs"]

                result1 = create_index.delay(
                    structure=structure,
                    laboratories=laboratoires,
                    researcher=chercheurs,
                    django_enabler=True,
                )
                task_id1 = result1.task_id

                result2 = collect_data(
                    laboratories=laboratoires,
                    researcher=chercheurs,
                    django_enabler=True,
                )
                if result2[0] is not None:
                    task_id2 = result2[0].task_id
                else:
                    task_id2 = None
                if result2[1] is not None:
                    task_id3 = result2[1].task_id
                else:
                    task_id3 = None

                # créée dynamiquement le contexte de la collecte demandé lors de la validation du formulaire
                context = {
                    "form": form,
                }
                for task_content in ["task_id1", "task_id2", "task_id3"]:
                    if eval(task_content) is not None:
                        context[task_content] = eval(task_content)

                return render(
                    request, "admin/elasticHal/export_to_elastic.html", context=context
                )

            else:
                form = ExportToElasticForm()
                return render(
                    request, "admin/elasticHal/export_to_elastic.html", {"form": form}
                )
        else:
            # Get form instance
            form = ExportToElasticForm()
            # Return
            return render(
                request, "admin/elasticHal/export_to_elastic.html", {"form": form}
            )

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
            # print(f"structure: {structure}, laboratoires: {laboratoires}, chercheurs: {chercheurs}")
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

                if "TOUT" in request.POST.keys():
                    tachesChercheur, tachesLabo = [], []
                    indexes = get_index_list()

                    for ind, lab in enumerate(indexes):
                        laboratoire = lab[0].split("-")[1]
                        structure = lab[0].split("-")[0]
                        result1 = collect_laboratories_data2.delay(laboratoire)
                        result2 = collect_researchers_data2.delay(
                            struct=structure, idx=lab[0]
                        )
                        taches.append([ind, result1.task_id, result2.task_id])

                elif collectionLabo is True:
                    if chercheurs is True:
                        laboratoire = collection.split("-")[1]
                        structure = collection.split("-")[0]
                        result1 = collect_laboratories_data2.delay(laboratoire)
                        task_id1 = result1.task_id
                        result2 = collect_researchers_data2.delay(
                            struct=structure, idx=collection
                        )
                        task_id2 = result2.task_id

                    else:
                        result1 = collect_laboratories_data2.delay(
                            collectionLabo, False
                        )
                        task_id1 = result1.task_id
                        task_id2 = None

                # elif chercheurs == True:
                #     result2 = collect_researchers_data2 .delay(struct=structure, idx=collection)
                #     task_id2 = result2.task_id
                #     task_id1 = None

            else:
                pass  # pas sûr
            if len(taches) > 0:
                print(taches)
                return render(
                    request,
                    "admin/elasticHal/export_to_elasticLabs.html",
                    context={"form": form, "taches": taches},
                )
            elif task_id1 in locals():
                if task_id2 in locals():
                    return render(
                        request,
                        "admin/elasticHal/export_to_elasticLabs.html",
                        context={
                            "form": form,
                            "task_id1": task_id1,
                            "task_id2": task_id2,
                        },
                    )
                else:
                    return render(
                        request,
                        "admin/elasticHal/export_to_elasticLabs.html",
                        context={"form": form, "task_id1": task_id1},
                    )
            else:
                return render(
                    request,
                    "admin/elasticHal/export_to_elasticLabs.html",
                    context={"form": form},
                )
        else:
            form = PopulateLab()

        data = {"form": form}
        return render(request, "admin/elasticHal/export_to_elasticLabs.html", data)


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
            )  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(
                filter(None, csv_data)
            )  # supprime les lignes vides dans le fichier.

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
            )  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(
                filter(None, csv_data)
            )  # supprime les lignes vides dans le fichier.

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


class ResearcherAdmin(admin.ModelAdmin, ExportCsv):
    """
    Modèle de l'administration des chercheurs
    """

    list_display = ("ldapId", "name", "function", "lab")
    list_filter = (
        "structSirene",
        "lab",
        "function",
    )
    search_fields = ("name",)
    actions = ["export_as_csv"]

    def get_urls(self):
        """
        Initialise les urls du modèle ResearcherAdmin
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
        Permet de charger un fichier CSV dans la base de données du modèle Researcher
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
            )  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(
                filter(None, csv_data)
            )  # supprime les lignes vides dans le fichier.

            for x in csv_data:
                fields = x.split(";")
                Researcher.objects.update_or_create(
                    structSirene=fields[0],
                    ldapId=fields[1],
                    name=fields[2],
                    type=fields[3],
                    function=fields[4],
                    mail=fields[5],
                    lab=fields[6],
                    supannAffectation=fields[7],
                    supannEntiteAffectationPrincipale=fields[8],
                    halId_s=fields[9],
                    labHalId=fields[10],
                    idRef=fields[11],
                    structDomain=fields[12],
                    firstName=fields[13],
                    lastName=fields[14],
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
admin.site.register(Researcher, ResearcherAdmin)
