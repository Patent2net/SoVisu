from django import forms
from django.forms import models

class CreateCredentials(forms.Form):
    # Set choices to an empty list as it is a required argument.
        # f_more = forms.CharField()
        f_halId_s = forms.CharField(label='ID HAL (texte)')
        f_IdRef = forms.CharField(label='IdRef')
        f_orcId = forms.CharField(label='ORCID')
        f_more = forms.CharField(label='autres')

class validCredentials(forms.Form):

    def __init__(self,*args,**kwargs):
        halId_s = kwargs.pop('halId_s')
        idRef = kwargs.pop('idRef')
        orcId = kwargs.pop('orcId')

        super(validCredentials,self).__init__(*args,**kwargs)

        self.fields['f_halId_s'].initial = halId_s
        self.fields['f_halId_s'].disabled = True
        self.fields['f_IdRef'].initial = idRef
        self.fields['f_orcId'].initial = orcId
        self.fields['f_more'].initial = '0'

    # Set choices to an empty list as it is a required argument.
    f_more = forms.CharField()
    f_halId_s = forms.CharField(label='ID HAL (texte)')
    f_IdRef = forms.CharField(label='IdRef')
    f_orcId = forms.CharField(label='ORCID')


class validLabCredentials(forms.Form):
    def __init__(self,*args,**kwargs):
        halStructId = kwargs.pop('halStructId')
        rsnr = kwargs.pop('rsnr')
        idRef = kwargs.pop('idRef')

        super(validLabCredentials,self).__init__(*args,**kwargs)

        # Set choices from argument.
        self.fields['f_halStructId'].initial = halStructId
        self.fields['f_halStructId'].disabled = True
        self.fields['f_rsnr'].initial = rsnr
        self.fields['f_IdRef'].initial = idRef

    # Set choices to an empty list as it is a required argument.
    f_halStructId = forms.CharField(label='ID HAL (entier)', max_length=100, widget=forms.TextInput(attrs={'class' : 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))
    f_rsnr = forms.CharField(label='RSNR', max_length=100, widget=forms.TextInput(attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))
    f_IdRef = forms.CharField(label='IdRef', max_length=100, widget=forms.TextInput(attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))


class setGuidingKeywords(forms.Form):
    def __init__(self,*args,**kwargs):
        guidingKeywords = kwargs.pop('guidingKeywords')

        super(setGuidingKeywords,self).__init__(*args,**kwargs)

        str = ""
        for keyword in guidingKeywords:
            str += keyword + ";"

        if len(str) > 0:
            str = str[:-1]
        self.fields['f_guidingKeywords'].initial = str

    # Set choices to an empty list as it is a required argument.
    f_guidingKeywords = forms.CharField(label='Mot-clés orienteurs', max_length=100, widget=forms.TextInput(attrs={'class' : 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))


class search(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'val' in kwargs:
            val = kwargs.pop('val')

        super(search, self).__init__(*args, **kwargs)

    # Set choices to an empty list as it is a required argument.

    indexes = (
        ("*documents", "références"),
        ("*researchers*", "chercheurs"),
        ("*laboratories*", "laboratoires")
    )

    f_index = forms.ChoiceField(label='Collection', choices = indexes)

    f_search = forms.CharField(label='Recherche', max_length=100, widget=forms.TextInput(attrs={'class' : 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))



class ContactForm(forms.Form):
    BUG = 'b'
    FEEDBACK = 'fb'
    NEW_FEATURE = 'nf'
    OTHER = 'o'
    purpose_choices = (
        (NEW_FEATURE, 'Rajout de fonctionnalité'),
        (BUG, 'Signaler une erreur'),
        (FEEDBACK, 'Feedback'),
        (OTHER, 'Autre'),
    )

    nom = forms.CharField()
    email = forms.EmailField()
    objet = forms.ChoiceField(choices=purpose_choices)
    message = forms.CharField(widget=forms.Textarea(attrs={'cols': 40, 'rows': 5}))