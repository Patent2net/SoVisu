from spacy.lang.fr.stop_words import STOP_WORDS
import spacy
import requests

global nlp_fr
nlp_fr = spacy.load("fr_core_news_md")  # chargement du modèle dans Spacy

global nlp_en
nlp_en = spacy.load("en_core_web_md")


def keyword_from_teeft(txt, lang):
    headers = {
        'accept': 'application/json',
        # Already added when you pass json= but not when you pass data=
        # 'Content-Type': 'application/json',
    }

    # initialisations des variables pour stocker les requetes  json
    json_data_fr = list()
    json_data_en = list()

    if lang == "fr":
        json_data_fr.append({
            'id': 1,
            'value': txt
        })
        response = requests.post('https://terms-extraction.services.inist.fr/v1/teeft/fr', headers=headers,
                                 json=json_data_fr)
        if response.ok:
            data_fr = response.json()
            if len(data_fr) == 1:
                return data_fr[0]["value"]
            else:
                return []

        else:
            return []

    if lang == "en":
        data_en = []
        # Pour chaque document ayant un résumer en français anglais
        json_data_en.append({
            'id': 0,
            'value': txt
        })
        response = requests.post('https://terms-extraction.services.inist.fr/v1/teeft/en', headers=headers,
                                 json=json_data_en)
        if response.ok:
            data_en = response.json()
            if len(data_en) == 1:
                return data_en[0]["value"]
            else:
                return []
        else:
            return []


def return_entities(txt, lang):
    # Cette fonction renvois les entité nommée des abstract d'un document
    # Actuellement la fonction gére le français et l'anglais
    #

    entities_fr, entities_en = [], []
    # for index, doc in enumerate(docs):
    nlp_fr.Defaults.stop_words.add("-")
    if lang == "fr":
        nlp_ = nlp_fr(txt)

        entities_fr = [token.text for token in nlp_.ents if
                       not token.text.isdigit() and not token.text in nlp_fr.Defaults.stop_words]
        # if not token.is_punct and not token .like_num and not token .isdigit() and token not in nlp_fr .Defaults.stop_words]

        return entities_fr
        # vérifier les entités avec loterre et ne garder que celles qui matchent avec le complément d'info
        # curl -X 'POST' \
        #   'https://loterre-resolvers.services.inist.fr/v1/9SD/identify?indent=true' \
        #   -H 'accept: application/json' \
        #   -H 'Content-Type: application/json' \
        #   -d '[
        #   {
        #     "id": 1,
        #     "value": "Toulon"
        #   },
        #   {
        #     "id": 2,
        #     "value": "PACA"
        #   },
        #   {
        #     "id": 3,
        #     "value": "Sao Paulo"
        #   }
    if lang == "en":
        nlp_ = nlp_en(txt)
        entities_en = [token.text for token in nlp_.ents if
                       not token.text.isdigit() and not token.text in nlp_fr.Defaults.stop_words]
        # print("taille du texte " + str(len(txt)))
        return entities_en
