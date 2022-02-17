from SPARQLWrapper import SPARQLWrapper, JSON
import networkx as nx
from pprint import pprint
import matplotlib.pyplot as plt



def cycle(liste):
    tempo = []
    if len(liste) < 1:
        return None
    else:
        taille = len(liste) - 1
        for indice in range(taille):
            tempo.append((liste[indice], liste[indice + 1]))
        return tempo


## lets go
sparql = SPARQLWrapper("http://sparql.archives-ouvertes.fr/sparql")
sparql.setReturnFormat(JSON)


def getHalId_s(aureHalId):
    # start
    # auteur :Joseph
    # commentaire:  Cette fonction prend en paramètre la valeur aureHalId  et retourne la valeur authIdHal_s  associée
    # example: aureHalId(826859)=>vanessa-richard
    # end
    sparql.setQuery("""
    select ?p ?o
    where  {
    <https://data.archives-ouvertes.fr/author/%s> ?p ?o
    }""" % aureHalId)
    results = sparql.query().convert()
    extIds = [truc for truc in results['results']['bindings'] if
              truc['p']['value'] == "http://www.openarchives.org/ore/terms/isAggregatedBy"]

    authIdHal_s = extIds[0]['o']['value'].split('/')[-1]
    return authIdHal_s


def getExtId(authIdHal_s):
    #start
    #auteur :Joseph
    #commentaire:  Cette fonction prend en paramètre la valeur authidhal_s et retourne la valeur aureHalId associée
    #example: authIdHal_s(vanessa-richard)=>826859
    #end
    sparql.setQuery("""
    select ?p ?o
    where  {
    <https://data.archives-ouvertes.fr/author/%s> ?p ?o
    }""" % authIdHal_s)
    results = sparql.query().convert()
    extIds = [truc for truc in results['results']['bindings'] if
              truc['p']['value'] == "http://www.openarchives.org/ore/terms/aggregates"]
    aureHalId = int(extIds[0]['o']['value'].rsplit('/', 1)[1])
    return  aureHalId

def getLabel(label, lang):
    #start
    #auteur :Joseph
    #commentaire:  Cette fonction prend en paramètre la valeur label et lang  et retourne le nom complet du label en fonction de la langue associée
    #example: getLabel("phys","en") => Physics
    #end
    sparql.setQuery("""
        select ?p ?o
        where  {
        <https://data.archives-ouvertes.fr/subject/%s> ?p ?o
        }""" % label)
    results = sparql.query().convert()

    label = [truc['o']['value'] for truc in results['results']['bindings'] if
             truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#prefLabel" if
             truc['o']['xml:lang'] == lang]
    label_complet = label[0]
    return label_complet


def getArticle(halId_s):
    # start
    # auteur :Joseph
    # commentaire: Cette fonction prend en paramètre halId_s l'id d'un article  et retourne sous forme de dictionnaire metadone_article qui regroupe l'ensemble des metadoné de l'article
    # example: getArticle(702215) => {'head': {'link': [], 'vars': ['p', 'o']}, 'results': {'distinct': False, 'ordered': True, 'bindings': []}}
    # end
    """returns  Liste des métadonnées d'un document in sparlq dataarchive format"""
    sparql.setQuery("""select ?p ?o 
where {
 <https://data.archives-ouvertes.fr/document/%s> ?p ?o
} """ % halId_s)
    results = sparql.query().convert()
    metadone_article = results
    return metadone_article


def recupIndividu(authIdHal_s):
    # start
    # auteur :Joseph
    # commentaire: Cette fonction prend en paramètre authIdHal_s  s d'un cherhcheur   et retourne sous forme de dictionnaire donnee_individu qui regroupe  l'ensemble des donnée concernant le chercheur
    # example: recupIndividu("vanessa-richard") => {'head': {'link': [], 'vars': ['p', 'o']}, 'results': {'distinct': False, 'ordered': True, 'bindings': [{'p': {'type': 'uri', 'value': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'} ....
    # end
    sparql.setQuery("""
select ?p ?o
where  {
<https://data.archives-ouvertes.fr/author/%s> ?p ?o
}""" % authIdHal_s)
    results = sparql.query().convert()
    # result in form of predicat, objet in a list in results['results']['bindings']
    donnee_individu = results
    return donnee_individu


def exploreBroader(uri):

    sparql.setQuery("""
    select ?p ?o
    where  {<%s> ?p ?o }""" % uri)


    results = sparql.query().convert()

    concepts = [truc for truc in results['results']['bindings'] if
                truc['p']['value'] == "http://purl.org/dc/elements/1.1/identifier"]
    # filtres par langues
    dicoTop = dict()

    dicoTop= [top['o']['value'] for top in concepts]
    broader = [truc['o']['value'] for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#broader"]

    if len(broader) > 0:
        for broad in broader:
            dicoTop.insert(0, exploreBroader(broad))

    return dicoTop

def extraitSujetsDomaines(data):
    """ inputs from recupIndividu(halidint)
    halidint est un individu
    """
    # extraction des résultats
    topics = [truc for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/topic_interest"]
    sujets = [truc['o']['value'] for truc in data['results']['bindings'] if
              truc['p']['value'] == "http://xmlns.com/foaf/0.1/interest"]
    # récupération des langues

    # alaric :  soit on considère que les mots qui n'ont pas de langue renseignée sont en anglais (j'ai constaté ça pour chl)
    # soit on les drop ?
    for top in topics:
        if 'xml:lang' not in top['o']:
            top['o']['xml:lang'] = 'en'

    # topics = [top for top in topics if 'xml:lang' in top['o']]

    langues = list(set([top['o']['xml:lang'] for top in topics]))
    # filtres par langues
    dicoTop = dict()

    for lang in langues:
        dicoTop[lang] = [top['o']['value'] for top in topics if top['o']['xml:lang'] == lang]

    return dicoTop, list(set(sujets))


def ExplainDomains(domUri):
    sparql.setQuery("""
    prefix foaf: <http://xmlns.com/foaf/0.1/>
    prefix skos: <http://www.w3.org/2004/02/skos/core>
    select ?p ?o
    where  {
    <%s> ?p ?o
    }""" % domUri)

    results = sparql.query().convert()

    langues = [truc['o']['xml:lang'] for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#prefLabel"]
    labels = dict()
    labels = [truc['o']['value'] for truc in results['results']['bindings'] if
              truc['p']['value'] == "http://purl.org/dc/elements/1.1/identifier"]
    broader = [truc['o']['value'] for truc in results['results']['bindings'] if
               truc['p']['value'] == "http://www.w3.org/2004/02/skos/core#broader"]


    if len(broader) > 0:

        tempo = []

        for broad in broader:
            res = exploreBroader(broad)
            for r in res:
                tempo.append(r)

        tempo.append(labels)

        tempo_clone = []

        for temp in tempo:
            if isinstance(temp, str):
                tempo_clone.append([temp])
            else:
                tempo_clone.append(temp)

        return tempo_clone
    else:
        return [labels]


def extraitMotsCles(dat):
    """ inputs from getArticle(halid)
    halid est un article
    """
    # extraction des résultats

    topics = [truc for truc in dat['results']['bindings'] if
              truc['p']['value'] == "http://purl.org/dc/elements/1.1/subject"]
    # sujets = [truc ['o']['value'] for truc in dat['results']['bindings'] if truc ['p']['value'] == "http://xmlns.com/foaf/0.1/interest"]
    # récupération des langues
    langues = list(set([top['o']['xml:lang'] for top in topics]))
    # filtres par langues
    dicoTop = dict()

    for lang in langues:
        dicoTop[lang] = [top['o']['value'] for top in topics if top['o']['xml:lang'] == lang]

    return dicoTop


# tests
# Extraction des mots clés d'un article
# à faire valider par article
# res = getArticle("hal-00000001v2")

# print (extraitMotsCles (res) )
# print (extraitMotsCles (res) )


def getConceptsAndKeywords(aureHalId):
    # start
    # auteur :Joseph
    # commentaire: Cette fonction prend en paramètre aureHalId  d'un chercheur   et retourne sous forme de dictionnaire ConceptsAndKeywords  qui regroupe  l'ensemble des concept et donnée aborder par le chercheur
    # example: getConceptsAndKeywords(702215) => {'fr': ['Toxines', 'Génétique des populations', 'Écologie microbienne', 'Cyanobactéries']}
    # end

    concept = []
    keywords = []

    # extraction des sujets d'intérêt et domaines d'un chercheur
    data = recupIndividu(aureHalId)

    sujets, domaines = extraitSujetsDomaines(data)
    Domains = []

    print (sujets, domaines)
    try:

        for dom in domaines:
            Domains.append(ExplainDomains(dom))


            # réseau json hiérarchiques
            #
            dicoNoeuds = dict()
            tree = nx.DiGraph()

            tree.add_node('Concepts')
            Domains = [list(filter(lambda x: x != None, truc)) for truc in Domains]

            for dom in Domains:
                tree.add_node(dom[0][0])
                tree.add_edge('Concepts', dom[0][0])
                if len(dom) > 1:
                    tree.add_node(dom[1][0])
                    tree.add_edge(dom[0][0], dom[1][0])
                if len(dom) > 2:
                    tree.add_node(dom[2][0])
                    tree.add_edge(dom[1][0], dom[2][0])

        concepts = nx.tree_data(tree, "Concepts")
        # with open(lang + "-concepts.json", "w", encoding='utf8') as ficRes:
        #     ficRes.write(str(nx.tree_data(tree, "Concepts")).replace("'", '"'))


        for children in concepts['children']:
            children['label_en'] = getLabel(children['id'], 'en')
            children['label_fr'] = getLabel(children['id'], 'fr')
            children['state'] = 'invalidated'
            if 'children' in children:
                for subchildren in children['children']:
                    subchildren['label_en'] = getLabel(subchildren['id'], 'en')
                    subchildren['label_fr'] = getLabel(subchildren['id'], 'fr')
                    subchildren['state'] = 'invalidated'
                    if 'children' in subchildren:
                        for subsubchildren in subchildren['children']:
                            subsubchildren['label_en'] = getLabel(subsubchildren['id'], 'en')
                            subsubchildren['label_fr'] = getLabel(subsubchildren['id'], 'fr')
                            subsubchildren['state'] = 'invalidated'


        for lang in sujets.keys():

            treeWords = nx.DiGraph()
            treeWords.add_node(lang)
            for kwd in sujets[lang]:
                treeWords.add_node(kwd)
                treeWords.add_edge(lang, kwd)
            keywords.append({'lang': lang, 'keywords': nx.tree_data(treeWords, lang)})
            # with open(lang + "-words.json", "w", encoding='utf8') as ficRes:
            #    ficRes.write(str(nx.tree_data(treeWords, lang)).replace("'", '"'))
        ConceptsAndKeywords ={'concepts': concepts, 'keywords': keywords}
        return ConceptsAndKeywords

    except:
        ConceptsAndKeywords= {'concepts': [], 'keywords': []}
        return  ConceptsAndKeywords
