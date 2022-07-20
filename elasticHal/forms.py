from django import forms
from .views import get_index_list


class CsvImportForm(forms.Form):
    """
    Form to import a csv file into the Django database
    :return:
    """
    csv_upload = forms.FileField()


class PopulateLab(forms.Form):
    """
    Form to populate a lab index or/and researchers index with documents
    :return:
    """
    def __init__(self, *args, **kwargs):
        indexes = get_index_list()
        super(PopulateLab, self).__init__(*args, **kwargs)

        self.fields['f_index'] = forms.ChoiceField(widget=forms.RadioSelect, label='Laboratoire', choices=indexes)  # self.fields[''] permet de rendre dynamique les champs du formulaire
        self.fields['collectionLabo'] = forms.BooleanField(initial=False, required=False)
        self.fields['chercheurs'] = forms.BooleanField(initial=False, required=False)


class ExportToElasticForm(forms.Form):
    """
    Form to export a Structure/lab/researchers index from Django DB to elasticsearch
    :return:
    """
    Structures = forms.BooleanField(initial=True, required=False)
    Laboratoires = forms.BooleanField(initial=True, required=False)
    Chercheurs = forms.BooleanField(initial=True, required=False)
