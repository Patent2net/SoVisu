from spacy.lang.fr.stop_words import STOP_WORDS
import pke
import spacy
import requests




##############################################################################################################################
#Ce fichier contient deux fonction principale :

    #Une fonction permettant d'enrichir une list de document en ajoutant une liste de mots clés complémentaire
    #Cette liste de mots clés complémentaire peux être constitué de deux list  disctinct :
    #-Une première liste constituée des mots clés auquel les entités nommée on était soustraite
    #-Une seconde liste constituée de mots clés générer à partir des abstracts en français des documents

    # Une  fonction  qui renvois une liste de mots clés générer à partir des résumés en français des documents
    # Les mots clés sont obtenus à partir de l'api Teeft (https://objectif-tdm.inist.fr/2021/12/20/extraction-de-termes-teeft/s

###############################################################################################################################
"""
def extract_key_words(text,extractor):
    # Déclaration d'une fonction permettant de d'extraire les mots clés d'un texte
    try:
        extractor.load_document(input=text, language='fr', normalization="stemming")
        extractor.candidate_selection()
        extractor.candidate_weighting()
        keyphrases = extractor.get_n_best(n=5)
        list_keyword = list()
        for key_word in keyphrases:
            list_keyword.append(key_word[0])
        list_keyword = list(set(list_keyword))
        return list_keyword
    except Exception as e:
        return (e)


def exctract_enties(docs):
    #Cette fonction prend en entrer une liste de document pour chaque document avec un résumé en français génére une list de mots clés sans entité
    # à partir de spacy et pke
    #cette liste de mots clés est générer à partir de la librairie Pke
    print("début exctract_enties")
    extractor = pke.unsupervised.TopicalPageRank()
    nlp = spacy.load("fr_core_news_md")  # chargement du modéle dans Spacy
    nlp.Defaults.stop_words |= STOP_WORDS
    stop_word_list = {"nouvelles"}
    for index, doc in enumerate(docs):
        list_keyword =list()
        
        if "fr_keyword_s" in doc.keys():
            # Cette partie de la fonction est un traitement des mots clés existant dans le champ fr_keyword_s
            # Si le document possède des mots clés, ces mots clés sont concaténés pour être traité avec spacy 
            # À partir de la concaténation, on extrait les entités nommées  contenues dans les mots pour les 
            # filtrer dans la liste de mots clés
            join_keword = " ".join(doc["fr_keyword_s"])       
            nlp_ = nlp(join_keword)
            entites = [token.text for token in nlp_ if token.ent_type_ and not token.is_stop]
            particular_pos = [token.text for token in nlp_ if (token.pos_  in ("PROPN") or token.is_punct or token.is_space)]
            list_keyword = [keyword for keyword in doc["fr_keyword_s"] if keyword not in entites]
            list_keyword = [keyword for keyword in list_keyword if keyword not in particular_pos]
        

        if  "fr_abstract_s" in doc.keys():
            #Cette partie de la fonction génère une liste de mots clés à partir du champ fr_abstract_s.
            #Cette liste est générée avec la librairie PKE , une fois la liste de mots clés générer elle
            #est nettoyée en procédant à l'extraction des entités nommée ,Les entités nommée sont détectées
            #avec Spacy.
            abstract_keyword = extract_key_words(str(doc["fr_abstract_s"]), extractor)
            abstract_keyword = [keyword for keyword in abstract_keyword if keyword not in STOP_WORDS]
            abstract_keyword = [keyword for keyword in abstract_keyword if keyword not in stop_word_list]
            nlp_ = nlp(str(doc["fr_abstract_s"]))
            entites = [token.text for token in nlp_ if token.ent_type_ and not token.is_stop]
            abstract_keyword = [keyword for keyword in abstract_keyword if keyword not in entites]
            list_keyword.extend(abstract_keyword)

        list_keyword = list(set(list_keyword))
        doc["pke_keywords"]=list_keyword
    print("Fin exctract_enties")
    return docs

"""

def keyword_from_teeft(docs):

    # Cette fonction prend en entrer une liste de document pour chaque document avec un résumé en français ou un résumer en anglais
    # la fonction interroge l'api de teeft , l'api renvois une liste de mots clés décrivant le document en fonction de langue du résumer (français ou anglais )
    # Le résultat de la requête est stocké dans le champ teeft_keywords_fr  pour les mots clés français et teeft_keywords_en pour les mots clés anglais
    # Source de l'api : https://openapi.services.inist.fr/?urls.primaryName=Extraction%20de%20termes
    # utils : Outil de conversion de requête curl en divers langages python , c ,java: https: // curlconverter.com /

    headers = {
        'accept': 'application/json',
        # Already added when you pass json= but not when you pass data=
        # 'Content-Type': 'application/json',
    }

    # initialisations des variables pour stocker les requetes  json
    json_data_fr=list()
    json_data_en = list()
    for index , doc in enumerate(docs):

        #Pour chaque document ayant un résumer en français
        if "fr_abstract_s" in doc.keys():
            json_data_fr.append({
            'id': index,
            'value':doc["fr_abstract_s"][0]
        })

        # Pour chaque document ayant un résumer en français anglais
        if "en_abstract_s" in doc.keys():
            json_data_en.append({
                'id': index,
                'value': doc["en_abstract_s"][0]
            })

    response = requests.post('https://terms-extraction.services.inist.fr/v1/teeft/fr', headers=headers, json=json_data_fr)
    data_fr = response.json()

    response = requests.post('https://terms-extraction.services.inist.fr/v1/teeft/en', headers=headers,json=json_data_en)
    data_en = response.json()

    for value in data_fr:
        docs[int(value["id"])]["teeft_keywords_fr"]= value["value"]

    for value in data_en:
        docs[int(value["id"])]["teeft_keywords_en"] = value["value"]

    return(docs)


def return_entities(docs):
    #Cette fonction renvois les entité nommée des abstract d'un document
    # Actuellement la fonction gére le français et l'anglais
    #
    nlp_fr = spacy.load("fr_core_news_md")  # chargement du modéle dans Spacy
    nlp_fr.Defaults.stop_words |= STOP_WORDS

    nlp_en = spacy.load("en_core_web_md")

    for index, doc in enumerate(docs):
        if "fr_abstract_s" in doc.keys():
            nlp_ = nlp_fr(str(doc["fr_abstract_s"]))
            doc["entities_fr"] = [token.text for token in nlp_ if token.ent_type_ and not token.is_stop]

        if "en_abstract_s" in doc.keys():
            nlp_ = nlp_en(str(doc["en_abstract_s"]))
            doc["entities_en"] = [token.text for token in nlp_ if token.ent_type_ and not token.is_stop]

    return(docs)