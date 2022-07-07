Installation
=====



SoVisu est un projet s'appuyant sur le `framework Django <https://www.djangoproject.com>`_ et qui est constitué de 2 applications:

- elasticHal, qui est chargé de récupérer les informations concernant les chercheurs ainsi que les laboratoires sur les `archives ouvertes HAL <https://hal.archives-ouvertes.fr>`_.

- sovisuhal, qui permet de retranscrire les données récupérées au sein d'une interface permettant aux chercheurs et laboratoires de gérer leur rayonnement numérique.

Les données récupérées sont stockées sur un Moteur de recherche `Elasticsearch <https://www.elastic.co/fr/elasticsearch/>`_, couplé à l'interface utilisateur `Kibana <https://www.elastic.co/fr/kibana/>`_ qui est utilisée pour créer les tableaux de bord proposés aux utilisateurs.

Mise en route
------------------------------------
Afin d'initialiser le projet, il est nécessaire de disposer d'une machine équipée de Python (version 3.9=~), de Docker, ainsi que de Git.

Il n'est pas nécessaire de créer des index pour Elasticsearch, ces derniers sont créés par elasticHal lors de la collecte.

Le code de SoVisu est accessible sur https://github.com/Patent2net/SoVisu .

Configuration de l'environnement
^^^^^^^^^^^^^^
1. Clonez le répertoire

.. code-block:: console

   (.venv) $ git clone https://github.com/Patent2net/SoVisu/

2. installez les requirements dans le projet SoVisu

.. code-block:: console

   (.venv) $ pip install -r requirements.txt

3. Dans doc/VisuStack, créer le dossier ``volume`` ainsi que les sous-dossiers ``backup1``, ``data1``, ``data2`` et ``MB-data``.


4. Exécutez la commande suivante pour installer l'environnement Elastic utilisé par le projet:

.. code-block:: console

   (.venv) $ docker-compose doc/VisuStack/docker-compose.yml

.. warning::
    Cette commande peut prendre du temps à s'exécuter, car elle télécharge les images Docker manquantes afin d'installer Kibana et ElasticSearch.


5. Initialisez les migrations de SoVisu:

.. code-block:: console

   (.venv) $ python manage.py migrate

6. Désignez le serveur CAS de l'institution:

.. code-block:: console

   (.venv) $ python manage.py add_institution "nom de l'institution" https://cas.exemple.fr


Vérification de l'installation
^^^^^^^^^^^^^^

1. Lancez SoVisu:

.. code-block:: console

   (.venv) $ python manage.py runserver

2. Visitez l'adresse suivante: http://127.0.0.1:8000/

3. Si la fenêtre affichée correspond à l'image ci-dessous, l'installation est effectuée.
[Rajouter image login Sovisu]

Mise en production
------------------------------------
(à compléter)