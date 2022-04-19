from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from .models import Structure, Laboratory, Researcher
from django import forms


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class StructureAdmin(admin.ModelAdmin):
    list_display = ('structSirene', 'acronym', 'label')

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]
            csv_name = request.FILES["csv_upload"].name  # will be used to check which split is needed and also the fields to complete
            print(csv_name)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # split by line

            csv_data.pop(0)  # delete the header of the csv

            for x in csv_data:
                fields = x.split(",")
                created = Structure.objects.update_or_create(
                    structSirene=fields[0],
                    label=fields[1],
                    acronym=fields[2],
                    domain=fields[3],

                )
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ('acronym', 'label', 'idRef')

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]
            csv_name = request.FILES["csv_upload"].name  # will be used to check which split is needed and also the fields to complete
            print(csv_name)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # split by line

            csv_data.pop(0)  # delete the header of the csv

            for x in csv_data:
                fields = x.split(";")
                created = Laboratory.objects.update_or_create(
                    structSirene=fields[0],
                    acronym=fields[1],
                    label=fields[2],
                    halStructId=fields[3],
                    rsnr=fields[4],
                    idRef=fields[5],
                )
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


class ResearcherAdmin(admin.ModelAdmin):
    list_display = ('ldapId', 'name', 'function', 'lab')

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]
            csv_name = request.FILES["csv_upload"].name  # will be used to check which split is needed and also the fields to complete
            print(csv_name)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")  # split by line

            csv_data.pop(0)  # delete the header of the csv

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
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


# Register your models here.
admin.site.register(Structure, StructureAdmin)
admin.site.register(Laboratory, LaboratoryAdmin)
admin.site.register(Researcher, ResearcherAdmin)
