Installation
=============

SoVisu est un projet s'appuyant sur le `framework Django <https://www.djangoproject.com>`_ et qui est constitué de 2 applications:

- elasticHal, qui est chargée de récupérer les informations les structures et les laboratoires.

- sovisuhal qui collecte les identifiants chercheurs, les métadonnées de leurs publications sur Hal pour présenter l

Les données récupérées sont stockées sur un moteur de recherche `Elasticsearch <https://www.elastic.co/fr/elasticsearch/>`_, couplé à l'interface utilisateur `Kibana <https://www.elastic.co/fr/kibana/>`_ qui est utilisée pour créer les tableaux de bord proposés aux utilisateurs.

Prérequis
-------------
Afin d'initialiser le projet, il est nécessaire de disposer d'une machine équipée de Python (version 3.9=~), de Docker, ainsi que de Git.

Il n'est pas nécessaire de créer des index pour Elasticsearch, ces derniers sont créés par elasticHal lors de la collecte.

Le code de SoVisu est accessible sur https://github.com/Patent2net/SoVisu . Ce qui suit suppose que vous ayez installé un environnement virtuel python noté ```venv``` par la suite avec les librairies du fichier requirements.txt (point 2 de la procédure).

Configuration de l'environnement
---------------------------------
1. Clonez le répertoire

.. code-block:: console

   (.venv) $ git clone https://github.com/Patent2net/SoVisu/

2. installez les requirements dans le projet SoVisu

.. code-block:: console

   (.venv) $ pip install -r requirements.txt

3. Dans doc/VisuStack, créer le dossier ``volume`` ainsi que les sous-dossiers ``backup1``, ``data1``, ``data2``, ``data3`` et ``MB-data``.


4. Exécutez la commande suivante pour installer l'environnement serveur utilisé par le projet:

.. code-block:: console

   (.venv) $ docker-compose doc/VisuStack/docker-compose.yml

.. warning::
    Cette commande peut prendre du temps à s'exécuter, car elle télécharge les images Docker de Kibana, ElasticSearch et Redis qui sont nécessaires au fonctionnement du projet.

SoVisu s'appuie sur une architecture telle la figure ci-dessous: Docker héberge tous les services supports excepté le serveur Django. Nginx sert de frontal de sécurité à tous les services y compris SoVisu.

.. image:: images/SoVisu-Architecture.drawio.png
    :width: 600px
    :align: center


5. Initialisez les migrations de SoVisu:

5.1 Adapter les variables d'environnement
5.2 Migration
.. code-block:: console

   (.venv) $ python manage.py migrate

6. Désignez le serveur CAS de l'institution:

.. code-block:: console

   (.venv) $ python manage.py add_institution "nom de l'institution" https://cas.exemple.fr

7. Créez un profil administrateur:

.. code-block:: console

   (.venv) $ python manage.py createsuperuser

.. tip::
    il vous sera demandé de rentrer un identifiant, une adresse mail et un mot de passe.
    Bien que l'identifiant et le mot de passe soient obligatoires, le champ adresse mail est optionnel.


Mise en route
-------------
.. warning::
    Avant toute mise en route de SoVisu, vérifiez que l'instance elastic avec lequel le projet interagit est active.
    Si ce n'est pas le cas, SoVisu renverra un message d'erreur au lieu de s'initialiser normalement.

Initialisation des processus dans la partie Admin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Lancez SoVisu:

.. code-block:: console

   (.venv) $ python manage.py runserver

2. Visitez l'adresse suivante: http://127.0.0.1:8000/admin/

3. Renseignez les identifiants administrateur créés précédemment.

En arrivant dans l'interface d'administration, vous pouvez voir les différentes Applications de SoVisu:
    - "Authentification et autorisation", qui est présente par défaut dans Django. Elle permet de gérer les utilisateurs se connectant avec des identifiants créés depuis l'interface administrateur ou avec des commandes depuis manage.py.
    - "Elastichal", qui permet d'initialiser la base de données Elasticsearch.
    - "Uniauth", qui permet dans le cas d'une installation dans une institution de gérer la connection à partir des identifiants CAS.

.. image:: images/affichage_admin.png
   :width: 600px
   :align: center

Dans la partie "Elastichal", trois modèles sont disponibles:
    - "Chercheurs", qui permet de stocker les informations de base concernant les objets chercheurs.
    - "Laboratoires", qui permet de stocker les informations de base concernant les objets laboratoires.
    - "Structures", qui permet de stocker les informations de base concernant les objets structures institutionnelles dont dépendent les laboratoires.

4. Cliquez sur "Chercheurs" dans l'onglet "Elastichal".

.. image:: images/visualisation_menu_elastichal.png
   :width: 800px
   :align: center

Le menu des modèles présent dans l'application Elastichal vous propose plusieurs options disponibles en cliquant sur les boutons situés en haut à droite de l'écran:
    - "Peupler Elastic", permet d'initialiser la base de données Elasticsearch à partir des données présentes dans les modèles Elastichal.
    - "Mettre à jour Elastic", permet de mettre à jour les données présentes dans Elasticsearch à partir des données présentes dans les modèles Elastichal.
    - "Importer des données", permet d'importer des données dans le modèle à partir d'un fichier CSV.
    - "Ajouter chercheur", permet d'ajouter un chercheur manuellement dans le modèle.

Dans le cas de la mise en route de SoVisu, nous allons importer des données à partir d'un fichier CSV.

5. Cliquez sur "Importer des données". Sur la page suivante il vous sera demandé d'importer un fichier. Il est important que celui ci soit au format CSV, et qu'il contienne des champs précis en fonction du modèle à remplir (voir les astuces ci dessous pour plus de détails).

.. tip::
    Dans le cas du modèle "Chercheurs", le fichier csv devra contenir les colonnes suivante:
    *structSirene, ldapId, name, type, function, mail, lab, supannAffectation,*
    *supannEntiteAffectationPrincipale, halId_s, labHalId, idRef, structDomain, firstName, lastName, aurehalId*

    exemple de fichier CSV Chercheurs:

    .. csv-table::
        :align: center
        :file: csv_demo/researchers.csv
        :header-rows: 1

.. tip::
    Dans le cas du modèle "Laboratoires", le fichier csv devra contenir les colonnes suivante:
    *structSirene; acronym; label; halStructId; rsnr; idRef*

    exemple de fichier CSV Laboratoires:

    .. csv-table::
        :align: center
        :file: csv_demo/laboratories.csv
        :delim: ;
        :header-rows: 1

.. tip::
    Dans le cas du modèle "Structures", le fichier csv devra contenir les colonnes suivante:
    *structSirene, label, acronym, domain*

    exemple de fichier CSV structures:

    .. csv-table::
        :align: center
        :file: csv_demo/structures.csv
        :header-rows: 1

6. Répétez l'opération pour les autres modèles dans Elastichal.

7. Une fois les trois modèles complétés, retournez sur le menu d'un des modèles Elastichal et cliquez sur "Peupler Elastic".

.. image:: images/peupler_elastic.png
    :width: 800px
    :align: center

8. Par défaut, "Peupler elastic" propose de remplir la base de données Elasticsearch avec les données présentes dans les modèles Structures, Laboratoires et Chercheurs.
    Cliquez sur "soumettre" afin de lancer le processus de collecte, Il est possible de voir l'état de la collecte dans la partie "Progression" de la page.

.. warning::
    Lors d'une première mise en route, il est impératif de lancer "peupler elastic" avec l'ensemble des modèles remplis.
    Le modèle structure permet de délimiter la récupération dans le cas ou les laboratoires et/ou chercheurs seraient recensés dans plusieurs structures.
    La récupération des données dans Elasticsearch est longue, et peut prendre du temps.
.. tip::
    La fonction "peupler elastic" peut également être utilisée par la suite pour mettre à jour en masse l'ensemble des données d'un ou de l'ensemble des modèles proposés par SoVisu:
    celle ci se base sur les données des modèles présent dans Django mais également les éléments déjà importés dans Elasticsearch.
    Pour cela, il suffit de sélectionner la partie qui doit être mise à jour pour lancer un processus allégé.

Spécificités de la mise en route de SoVisu pour le développement
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Dans le cas d'une installation de SoVisu sur une machine de développement n'ayant pas accès à l'authentification par CAS, il est nécessaire de définir un profil utilisateur afin d'accéder à l'application.
Dans le cas d'un profil chercheur, celui ci est identifié par SoVisu grâce à son identifiant ldapId. Le nom d'utilisateur est le même que l'identifiant ldapId.

Il est cependant possible de définir un profil utilisateur nommé "adminlab", reconnu par SoVisu comme un administrateur du laboratoire et ayant donc accès complet à l'application.

1. Dans l'interface d'administration de SoVisu, cliquez sur "Utilisateurs" dans "Authentification et autorisations".
2. Cliquez sur "Ajouter utilisateur".
3. Créez un utilisateur ayant pour nom d'utilisateur "adminlab", le mot de passe est libre de choix.
4. Cliquez sur "Enregistrer".

Initialisation des visualisations dans Kibana
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Dans Kibana, il est possible de créer des visualisations à partir des données présentes dans Elasticsearch.
Par défaut SoVisu propose des visualisations qui sont disponibles dans les dossiers du projet:
SoVisu/doc/Dashboards/

Afin de les rendre disponible il est nécessaire de les importer dans l'instance Kibana dont dépend votre installation.

1. Dans Kibana, ouvrez le menu.
2. Dans la section Management, cliquez sur "Stack Management"
3. Sur la nouvelle page affichée, allez dans "Saved Objects"(dans la section Kibana).
4. Cliquez sur "Import" et importez les fichiers disponibles dans le dossier SoVisu/doc/Dashboards/, en sélectionnant  les options "check for existing objects" et "automatically overwrite conflicts".
5. Cliquez sur "import".
6. Kibana vous signale l'ensemble des objets modifiés; Cliquez sur "Done"
7. répétez les points 4 à 6 pour l'ensemble des fichiers dans le dossier.

Mise en production
-------------------
.. warning::
    à compléter
