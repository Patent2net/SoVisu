from django import forms
from .views import get_index_list


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class PopulateLab(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'val' in kwargs:
            val = kwargs.pop('val')

        super(PopulateLab, self).__init__(*args, **kwargs)
    indexes = get_index_list()
    f_index = forms.ChoiceField(widget=forms.RadioSelect, label='Laboratoire', choices=indexes)
    collectionLabo = forms.BooleanField(initial=False, required=False)
    chercheurs = forms.BooleanField(initial=True, required=False)

    #f_search = forms.CharField(label='Peuplement entités', max_length=100, widget=forms.TextInput(
    #   attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))


class ExportToElasticForm(forms.Form):
    Structures = forms.BooleanField(initial=True, required=False)
    Laboratoires = forms.BooleanField(initial=True, required=False)
    Chercheurs = forms.BooleanField(initial=True, required=False)