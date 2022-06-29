from __future__ import absolute_import, unicode_literals
import csv
from django.contrib import admin, messages
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
from .models import Structure, Laboratory, Researcher
from django import forms

from .insert_entities import create_index
from .collect_from_HAL import collect_data, init_labo, collect_laboratories_data2, collect_researchers_data2

admin.site.site_header = "Administration de SoVisu"


# Celery
from celery import shared_task

# Celery-progress
from celery_progress.backend import ProgressRecorder

class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class ExportToElasticForm(forms.Form):
    Structures = forms.BooleanField(initial=True, required=False)
    Laboratoires = forms.BooleanField(initial=True, required=False)
    Chercheurs = forms.BooleanField(initial=True, required=False)


class PopulateLab(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'val' in kwargs:
            val = kwargs.pop('val')

        super(PopulateLab, self).__init__(*args, **kwargs)

    # Set choices to an empty list as it is a required argument.
    labos, dico_acronym = init_labo()
    structur = "198*-" # on doit pouvoir faire un init_struct
    indexes = [] # ("198*-" + labos [ind] + "*-laboratories", dico_acronym  [ind]) ))

    for labId in dico_acronym .keys():
            idx = structur + labId + "-laboratories"

            indexes.append((idx, dico_acronym [labId] ))
    indexes = tuple(indexes)
    f_index = forms.ChoiceField(widget=forms.RadioSelect, label='Laboratoire', choices=indexes)
    collectionLabo = forms.BooleanField(initial=False, required=False)
    chercheurs = forms.BooleanField(initial=True, required=False)

    #f_search = forms.CharField(label='Peuplement entités', max_length=100, widget=forms.TextInput(
     #   attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))


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


# Models are under that line+



class StructureAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('structSirene', 'acronym', 'label')
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [
            path('upload-csv/', self.upload_csv),
            path('export-elastic/', self.export_to_elastic),
        ]
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

    @staticmethod
    def export_to_elastic(request):

        if request.method == "POST":
            structure = request.POST.get('Structures')
            laboratoires = request.POST.get('Laboratoires')
            chercheurs = request.POST.get('Chercheurs')
            print(f"structure: {structure}, laboratoires: {laboratoires}, chercheurs: {chercheurs}")

            create_index(structure=structure, laboratories=laboratoires, researcher=chercheurs, csv_enabler=None, django_enabler=True)
            collect_data(laboratories=laboratoires, researcher=chercheurs, csv_enabler=None, django_enabler=True)

        form = ExportToElasticForm()
        data = {"form": form}
        return render(request, "admin/elasticHal/export_to_elastic.html", data)


class LaboratoryAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('acronym', 'label', 'halStructId', 'idRef', 'structSirene')
    list_filter = ('structSirene',)
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [
            path('upload-csv/', self.upload_csv),
            path('export-elastic/', self.export_to_elastic),
        ]
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

    @staticmethod
    def export_to_elastic(request):

        if request.method == "POST":
            form = PopulateLab(request.POST)
            # structure = request.POST.get('Structures')
            # laboratoires = request.POST.get('Laboratoires')
            # chercheurs = request.POST.get('Chercheurs')
            #  laboratoires =
            #print(f"structure: {structure}, laboratoires: {laboratoires}, chercheurs: {chercheurs}")
            if form .is_valid():
                if "chercheurs" in form. fields .keys():
                    chercheurs = True
                else:
                    chercheurs = False
                if "collectionLabo" in form.fields .keys():
                    collectionLabo = True
                else:
                    collectionLabo = False
                collection = form .cleaned_data ["f_index"]
                print('uuuu ', collection)
            laboratoire = collection . split("-")[1]
            structure = collection .split("-")[0]
            # chercheurs = True
            # create_index(structure=structure, laboratories=laboratoires, researcher=chercheurs, csv_enabler=None, django_enabler=True)
            if collectionLabo:
                if chercheurs:
                    result1 = collect_laboratories_data2 .delay(laboratoire)
                    task_id1 = result1.task_id
                    result2 = collect_researchers_data2.delay(struct=structure, idx=collection)
                    task_id2 = result2.task_id

                else:
                    result1 = collect_laboratories_data2 .delay(collectionLabo, False)
                    task_id1 = result1.task_id
                    task_id2 = None

            elif chercheurs:
                result2 = collect_researchers_data2 .delay(struct = structure, idx = collection )
                task_id2 = result2.task_id
                task_id1 = None

            else:
                pass # pas sûr

            return render(request, "admin/elasticHal/export_to_elasticLabs.html",
                          context={'form': form, 'task_id2': task_id2})
        form = PopulateLab()
        data = {'form': form
        }
        return render(request, "admin/elasticHal/export_to_elasticLabs.html", data)


class ResearcherAdmin(admin.ModelAdmin, ExportCsv):
    list_display = ('ldapId', 'name', 'function', 'lab')
    list_filter = ('structSirene', 'lab', 'function',)
    search_fields = ('name',)
    actions = ["export_as_csv"]

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [
            path('upload-csv/', self.upload_csv),
            path('export-elastic/', self.export_to_elastic),
        ]
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
                    aurehalId=fields[15],

                )
                print(created)
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/csv_upload.html", data)



    @staticmethod
    def export_to_elastic(request):

        if request.method == "POST":
            form = ExportToElasticForm(request.POST)
            if form.is_valid():
                structure = form.cleaned_data['Structures']
                laboratoires = form.cleaned_data['Laboratoires']
                chercheurs = form.cleaned_data['Chercheurs']
                print(f"structure: {structure}, laboratoires: {laboratoires}, chercheurs: {chercheurs}")
                result1 = create_index.delay(structure=structure, laboratories=laboratoires, researcher=chercheurs, csv_enabler=None, django_enabler=True)
                task_id1 = result1.task_id

                #print(f'Celery Task ID: {task_id1}')
                result2 = collect_data(laboratories=laboratoires, researcher=chercheurs, csv_enabler=None, django_enabler=True)
                if result2[0] is not None:
                    task_id2 = result2[0].task_id
                else:
                    task_id2 = None
                if result2[1] is not None:
                    task_id3 = result2[1].task_id
                else:
                    task_id3 = None

                #
                print(f'Celery Task ID2: {task_id2}')
                print(f'Celery Task ID3: {task_id3}')
                if (task_id3 is not None and task_id2 is not None and task_id1 is not None):
                    return render(request, "admin/elasticHal/export_to_elastic.html", context={'form': form, 'task_id1': task_id1, 'task_id2': task_id2, 'task_id3': task_id3})
                if (task_id2 is not None and task_id1 is not None):
                    return render(request, "admin/elasticHal/export_to_elastic.html",
                                  context={'form': form, 'task_id1': task_id1, 'task_id2': task_id2})
                if (task_id3 is not None and task_id2 is not None):
                    return render(request, "admin/elasticHal/export_to_elastic.html",
                                  context={'form': form, 'task_id2': task_id2,
                                           'task_id3': task_id3})
                if (task_id3 is not None and task_id1 is not None):
                    return render(request, "admin/elasticHal/export_to_elastic.html",
                                  context={'form': form, 'task_id1': task_id1,
                                           'task_id3': task_id3})

                if task_id1 is not None:
                    return render(request, "admin/elasticHal/export_to_elastic.html", context={'form': form, 'task_id1': task_id1})
                if task_id2 is not None:
                    return render(request, "admin/elasticHal/export_to_elastic.html", context={'form': form, 'task_id2': task_id2})
                if task_id3 is not None:
                    return render(request, "admin/elasticHal/export_to_elastic.html", context={'form': form, 'task_id3': task_id3})
                else:
                    return render(request, "admin/elasticHal/export_to_elastic.html", context={'form': form})
            else:
                form = ExportToElasticForm()
                return render(request, 'admin/elasticHal/export_to_elastic.html', {'form': form})
        else:
            # Get form instance
            form = ExportToElasticForm()
            # Return
            return render(request, 'admin/elasticHal/export_to_elastic.html', {'form': form})
        #form = ExportToElasticForm()


            #return render(request, "admin/elasticHal/export_to_elastic.html", data)




# Register your models here.
admin.site.register(Structure, StructureAdmin)
admin.site.register(Laboratory, LaboratoryAdmin)
admin.site.register(Researcher, ResearcherAdmin)
