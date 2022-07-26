from django import forms
from .views import get_index_list


class CsvImportForm(forms.Form):
    """
    Formulaire d'import de fichier CSV pour l'indexation dans Django
    """
    importer_un_fichier = forms.FileField()


class PopulateLab(forms.Form):
    """
    Formulaire pour initialiser la population d'un index laboratoire ou chercheur dans Elasticsearch
    """
    def __init__(self, *args, **kwargs):
        indexes = get_index_list()
        super(PopulateLab, self).__init__(*args, **kwargs)

        self.fields['f_index'] = forms.ChoiceField(widget=forms.RadioSelect, label='Laboratoire', choices=indexes)  # self.fields[''] permet de rendre dynamique les champs du formulaire
        self.fields['collectionLabo'] = forms.BooleanField(initial=False, required=False)
        self.fields['chercheurs'] = forms.BooleanField(initial=False, required=False)


class ExportToElasticForm(forms.Form):
    """
    Formulaire pour créer les index dans Elasticsearch à partir des données de Django et rechercher les documents dans l'API HAL
    """
    Structures = forms.BooleanField(initial=True, required=False)
    Laboratoires = forms.BooleanField(initial=True, required=False)
    Chercheurs = forms.BooleanField(initial=True, required=False)
