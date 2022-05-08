import csv

from django.contrib import admin, messages
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
from .models import Structure, Laboratory, Researcher
from django import forms

admin.site.site_header = "Administration de SoVisu"


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class ExportCsv:
    def export_as_csv(self, request, queryset):

        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        response.write(u'\ufeff'.encode('utf8'))

        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = writer.writerow([getattr(obj, field) for field in field_names])

        return response

    export_as_csv.short_description = "Exporter les éléments sélectionnés"


class StructureAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('structSirene', 'acronym', 'label')
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    @staticmethod
    def upload_csv(request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]

            if not csv_file.name.endswith('.csv'):
                messages.warning(request, "Le fichier importé n'est pas un .csv")
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # sépare le fichier par ligne

            csv_data.pop(0)  # supprime l'en-tête du csv

            csv_data = list(map(str.strip, csv_data))  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(filter(None, csv_data))  # supprime les lignes vides dans le fichier.

            for line in csv_data:
                fields = line.split(",")
                created = Structure.objects.update_or_create(
                    structSirene=fields[0],
                    label=fields[1],
                    acronym=fields[2],
                    domain=fields[3],

                )
                print(created)
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


class LaboratoryAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('acronym', 'label', 'halStructId', 'idRef', 'structSirene')
    list_filter = ('structSirene',)
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    @staticmethod
    def upload_csv(request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]

            if not csv_file.name.endswith('.csv'):
                messages.warning(request, "Le fichier importé n'est pas un .csv")
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # sépare le fichier par ligne

            csv_data.pop(0)  # supprime l'en-tête du csv

            csv_data = list(map(str.strip, csv_data))  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(filter(None, csv_data))  # supprime les lignes vides dans le fichier.

            for x in csv_data:
                fields = x.split(";")  # sépare les lignes en champs
                created = Laboratory.objects.update_or_create(
                    structSirene=fields[0],
                    acronym=fields[1],
                    label=fields[2],
                    halStructId=fields[3],
                    rsnr=fields[4],
                    idRef=fields[5],
                )
                print(created)
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


class ResearcherAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('ldapId', 'name', 'function', 'lab')
    list_filter = ('structSirene', 'lab', 'function',)
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    @staticmethod
    def upload_csv(request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]

            if not csv_file.name.endswith('.csv'):
                messages.warning(request, "Le fichier importé n'est pas un .csv")
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # sépare le fichier par ligne

            csv_data.pop(0)  # supprime l'en-tête du csv

            csv_data = list(map(str.strip, csv_data))  # enlève les caractères spéciaux tels que '\r' afin d'avoir le contenu exact des lignes

            csv_data = list(filter(None, csv_data))  # supprime les lignes vides dans le fichier.

            for x in csv_data:
                fields = x.split(",")
                created = Researcher.objects.update_or_create(
                    structSirene=fields[0],
                    ldapId=fields[1],
                    name=fields[2],
                    type=fields[3],
                    function=fields[4],
                    mail= fields[5],
                    lab=fields[6],
                    supannAffectation=fields[7],
                    supannEntiteAffectationPrincipale=fields[8],
                    halId_s=fields[9],
                    labHalId=fields[10],
                    idRef=fields[11],
                    structDomain=fields[12],
                    firstName=fields[13],
                    lastName=fields[14],
                    aurehalId=fields[15],

                )
                print(created)
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


# Register your models here.
admin.site.register(Structure, StructureAdmin)
admin.site.register(Laboratory, LaboratoryAdmin)
admin.site.register(Researcher, ResearcherAdmin)
