from spacy.lang.fr.stop_words import STOP_WORDS
import spacy
import requests




##############################################################################################################################
#Ce fichier contient deux fonction principale :

    # Une  fonction  qui renvois une liste de mots clés générer à partir des résumés en français des documents
    # Les mots clés sont obtenus à partir de l'api Teeft (https://objectif-tdm.inist.fr/2021/12/20/extraction-de-termes-teeft/s

    #Une fonction qui renvois les entités nommée d'un resumer en anglais ou  français. L'exctraction se fais à partir des modéles
    #fr_core_news_md pour le français et en_core_web_md pour l'anglai

###############################################################################################################################


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