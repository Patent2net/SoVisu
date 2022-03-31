from django import forms
from .libs import esActions

struct = "198307662"  # mesure temporaire, valable tant que seuls les chercheurs UTLN ont le droit de s'inscrire


class CreateCredentials(forms.Form):
    # Set choices to an empty list as it is a required argument.
    # f_more = forms.CharField()

    roles = [('chercheur', 'chercheur'), ('adminlab', 'responsable ou directeur de laboratoire'),
             ('visiteur', 'visiteur')
             ]
    f_role = forms.CharField(label='Role', widget=forms.Select(choices=roles))

    f_halId_s = forms.CharField(label='ID HAL (texte, par ex. david-reymond)')
    f_IdRef = forms.CharField(label='IdRef - identifiant de la notice champ facultatif', required=False)
    f_orcId = forms.CharField(label='ORCID (numéro sous la forme: 0000-0003-2071-6594) champ facultatif',
                              required=False)
    # f_more = forms.CharField(label='autres')

    es = esActions.es_connector()

    scope_param = esActions.scope_all()

    count = es.count(index=struct + "*-laboratories", body=scope_param)['count']
    res = es.search(index=struct + "*-laboratories", body=scope_param, size=count)
    entities = res['hits']['hits']
    # harvested_from_label.keyword
    # labos = []
    # for truc in entities:
    #     if 'halStructId' in truc ['fields'].keys():
    #         labos.append(truc ['fields']['halStructId'] [0])
    # labos = [((truc ['fields']['halStructId'] [0], truc ['fields']['acronym'] [0]), truc ['fields']['label'][0]) for truc in entities]
    labos = [((truc['_source']['halStructId'], truc['_source']['acronym']), truc['_source']['label']) for truc in
             entities]
    f_labo = forms.CharField(label='Labo', widget=forms.Select(choices=labos))


class ValidCredentials(forms.Form):

    def __init__(self, *args, **kwargs):
        halid_s = kwargs.pop('halId_s')
        idref = kwargs.pop('idRef')
        orcid = kwargs.pop('orcId')
        function = kwargs.pop('function')

        super(ValidCredentials, self).__init__(*args, **kwargs)

        self.fields['f_halId_s'].initial = halid_s
        self.fields['f_halId_s'].disabled = True
        self.fields['f_IdRef'].initial = idref
        self.fields['f_orcId'].initial = orcid
        self.fields['f_more'].initial = '0'
        self.fields['f_status'].initial = function

    status = (
        ("0", "Non renseigné"),
        ("Enseignant Contractuel", "Enseignant Vacataire"),
        ("Enseignant Titulaire", "Enseignant Titulaire"),
        ("Enseignant Contractuel", "Enseignant Contractuel"),
        ("Personnel Administratif ou Technique Contractuel", "Personnel Administratif ou Technique Contractuel"),
        ("Enseignant Chercheur Titulaire", "Enseignant Chercheur Titulaire"),
        ("Doctorant", "Doctorant"),
        ("Emérite", "Emérite"),
        ("Personnel Hébergé", "Personnel Hébergé")
    )

    # Set choices to an empty list as it is a required argument.
    f_more = forms.CharField()
    f_halId_s = forms.CharField(label='ID HAL (texte)')
    f_status = forms.ChoiceField(label='Statut', choices=status)
    f_IdRef = forms.CharField(label='IdRef', required=False)
    f_orcId = forms.CharField(label='ORCID', required=False)


class ValidLabCredentials(forms.Form):
    def __init__(self, *args, **kwargs):
        halstructid = kwargs.pop('halStructId')
        rsnr = kwargs.pop('rsnr')
        idref = kwargs.pop('idRef')

        super(ValidLabCredentials, self).__init__(*args, **kwargs)

        # Set choices from argument.
        self.fields['f_halStructId'].initial = halstructid
        self.fields['f_halStructId'].disabled = True
        self.fields['f_rsnr'].initial = rsnr
        self.fields['f_IdRef'].initial = idref

    # Set choices to an empty list as it is a required argument.
    f_halStructId = forms.CharField(label='ID HAL (entier)', max_length=100, widget=forms.TextInput(
        attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))
    f_rsnr = forms.CharField(label='RSNR', max_length=100, widget=forms.TextInput(
        attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))
    f_IdRef = forms.CharField(label='IdRef', max_length=100, widget=forms.TextInput(
        attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))


class SetGuidingKeywords(forms.Form):
    def __init__(self, *args, **kwargs):
        guiding_keywords = kwargs.pop('guidingKeywords')

        super(SetGuidingKeywords, self).__init__(*args, **kwargs)

        str_value = ""
        for keyword in guiding_keywords:
            str_value += keyword + ";"

        if len(str_value) > 0:
            str_value = str_value[:-1]
        self.fields['f_guidingKeywords'].initial = str_value

    # Set choices to an empty list as it is a required argument.
    f_guidingKeywords = forms.CharField(label='Mot-clés orienteurs', max_length=100, widget=forms.TextInput(
        attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none', 'size': 80}))


class SetResearchDescription(forms.Form):
    def __init__(self, *args, **kwargs):
        research_summary = kwargs.pop('research_summary')
        research_projects_in_progress = kwargs.pop('research_projectsInProgress')
        research_projects_and_fundings = kwargs.pop('research_projectsAndFundings')

        super(SetResearchDescription, self).__init__(*args, **kwargs)

        self.fields['f_research_summary'].initial = research_summary
        self.fields['f_research_projectsInProgress'].initial = research_projects_in_progress
        self.fields['f_research_projectsAndFundings'].initial = research_projects_and_fundings

    f_research_summary = forms.CharField(widget=forms.Textarea, required=False)
    f_research_projectsInProgress = forms.CharField(widget=forms.Textarea, required=False)
    f_research_projectsAndFundings = forms.CharField(widget=forms.Textarea, required=False)


class Search(forms.Form):

    def __init__(self, *args, **kwargs):
        if 'val' in kwargs:
            val = kwargs.pop('val')

        super(Search, self).__init__(*args, **kwargs)

    # Set choices to an empty list as it is a required argument.

    indexes = (
        ("*-researchers-*-doc*", "références"),
        ("*-researchers", "chercheurs"),
        ("*-laboratories", "laboratoires")
    )

    f_index = forms.ChoiceField(label='Collection', choices=indexes)

    f_search = forms.CharField(label='Recherche', max_length=100, widget=forms.TextInput(
        attrs={'class': 'flex text-sm py-1 px-2 border rounded border-gray-200 focus-none outline-none'}))
