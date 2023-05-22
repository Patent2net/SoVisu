======
SoVisu
======

Description
===========

SoVisu est un dispositif flexible et ouvert créé pour accompagner la communauté d'un établissement à la Science Ouverte (SO) en lui fournissant les instruments guides de son pilotage, tout en permettant de cartographier l'expertise des chercheurs, faciliter l'autoarchivage et apprécier la qualité de l'indexation.
Ce dispositif prend source sur HAL pour s'inscrire dans l'écosystème de la SO côté usager en donnant la possibilité aux chercheurs d'aligner leurs identifiants, de qualifier/vérifier et compléter leurs données bibliographiques, leurs domaines et leurs mot-clés "experts".

Utilisation personnelle
-----------------------

Pour un chercheur, SoVisu accompagne la vérification et le recensement des Id (idRef, OrcId, idHal), récupère sur [HAL](https://hal.science) les notices bibliographiques associées à sa production pour produire une synthèse et des cartographies lexicales (comparable à celles produites par les index). L'interface laisse la possibilité d'exclure de son profil certaines productions. SoVisu produit alors des tableaux de bord sous forme de visualisations dynamiques et interactives à partir des travaux (indicateurs bibliométriques interactifs, extractions lexicales), des liens directs vers HAL pour chacune des notices afin de corriger/compléter certaines données et des synthèses : chacun peut apprécier la qualité de sa représentation sur les index et éventuellement corriger.

Utilisation pilotage
--------------------

Pour un laboratoire, ou groupe de, côté gouvernance les mêmes principes et fonctions précédentes par agrégations, extractions de la production au format HCERES (4 premiers volets avec calculs réalisés : interrogation unpaywal, appartenance d'un doctorant dans les co-publiants notamment, attribution à des axes/équipes spécifiques). Les agrégations permettent alors d'opérer sur des données bibliographiques validées par les chercheurs.

Généralités
===========

Technologie
^^^^^^^^^^^^

SoVisu est une application web Python/Django se basant sur les données disponibles sur [HAL](https://hal.science) et constitué de deux applications distinctes :
  - **elasticHal** : chargée de récupérer les données des laboratoires et chercheurs sur HAL, puis de les enrichir, afin de les incorporer à une base de données Elastic. Accessible via l'interface administration de Django,
  - **sovisuhal** : chargée d'afficher les données aux utilisateurs et se basant sur un environnement Django. Présente les données HAL récupérées puis stockées dans Elastic.

Licence
^^^^^^^

EUPL_v1.2_fr.pdf

Code source
^^^^^^^^^^^^

Sur Git-hub : https://github.com/Patent2net/SoVisu

Documentation
^^^^^^^^^^^^

http://sovisu.readthedocs.io/
