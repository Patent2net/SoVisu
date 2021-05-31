from django import forms
from django.forms import models
from elasticsearch import Elasticsearch
from decouple import config

try:
    mode = config("mode")  # Prod --> mode = 'Prod' en env Var
    from decouple import config
except:
    mode = "Dev"
try:
    structId = config("structId")
except:
    structId = "198307662"  # UTLN

#struct = "198307662"

def esConnector(mode = mode):
    if mode == "Prod":
        secret = config ('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es

class CreateCredentials(forms.Form):
    # Set choices to an empty list as it is a required argument.
        # f_more = forms.CharField()

    roles = [('chercheur', 'chercheur'), ('adminlab', 'responsable ou directeur de laboratoire'),
             ('visiteur', 'visiteur')]
    f_role = forms.CharField(label='Role', widget=forms.Select(choices=roles))

    f_halId_s = forms.CharField(label='ID HAL (texte, par ex. david-reymond)')
    f_IdRef = forms.CharField(label='IdRef - identifiant de la notice')
    f_orcId = forms.CharField(label='ORCID (numéro par ex: 0000-0003-2071-6594')
    f_more = forms.CharField(label='autres')


    es = esConnector()

    scope_param = {
        "query": {
            "match_all": {}
        }
    }

    count = es.count(index=structId + "*-laboratories", body=scope_param)['count']
    scope_param = {
        "query": {
            "match_all": {}
        },
        "fields": [ 'acronym', "label", "idRef", "halStructId"]
    }
    res = es.search(index=structId + "*-laboratories", body=scope_param, size=count)
    entities = res['hits']['hits']
    ##harvested_from_label.keyword

    labos = [((truc ['fields']['halStructId'] [0], truc ['fields']['acronym'] [0]), truc ['fields']['label'][0]) for truc in entities]

    f_labo = forms.CharField(label='Labo', widget=forms.Select (choices=labos))



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
        (structId + "-*-documents", "références"),
        (structId + "-*-researchers", "chercheurs"),
        (structId + "-*-laboratories", "laboratoires")
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