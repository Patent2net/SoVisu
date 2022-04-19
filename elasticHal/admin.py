from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from .models import Structure, Laboratory, Researcher
from django import forms


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class ElastichalAdmin(admin.ModelAdmin):
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
            print(csv_data)

            for x in csv_data:  # uniquement pour laboratory pour le moment
                fields = x.split(";")  # le split doit être avec ";" pour laboratory et "," si researchers ou structures
                created = Laboratory.objects.update_or_create(
                    structSirene=fields[0],
                    acronym=fields[1],
                    label=fields[2],
                    halStructId=fields[3],
                    rsnr=fields[4],
                    idref=fields[5],
                )
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)


# Register your models here.
admin.site.register(Structure,)
admin.site.register(Laboratory, ElastichalAdmin)
admin.site.register(Researcher,)
