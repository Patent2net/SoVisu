# SoVisu


SoVisu est un dispositif créé et pensé pour accompagner la communauté d'un établissement à la Science Ouverte(SO) en lui fournissant les instruments guides de son pilotage, tout en permettant de cartographier l'expertise des chercheurs.
Ce dispositif prend source sur HAL pour s'inscrire dans l'écosystème de la SO côté usager en donnant la possibilité aux chercheurs de qualifier/vérifier et compléter leurs données de production, leurs domaines, leurs mot-clés "experts".

Pour un chercheur SoVisu accompagne la vérification et recensement des Id (idRef, OrcId, idHal), validation des données issues de scanr, récupération et intégration ou pas de sa production issue de Hal à son profil chercheur.
SoVisu produit alors un tableau de bord sous forme de visualisations dynamiques et interactives à partir des travaux (indicateurs bibliométriques interactifs).


Pour un laboratoire, ou groupe de, côté gouvernance les mêmes principes et fonctions par agrégations, extractions de la production au format HCERES (4 premiers volets avec calculs réalisés : interrogation unpaywal, appartenance d'un doctorant dans les co-publiants notamment).
Ainsi, SoVisu se positionne côté chercheur, sa production et son domaine d'expertise en ciblant qualité, fiabilité et accompagnement à l'ouverture des données.


SoVisu est une application web Python/Django se basant sur les données disponible sur HAL (https://hal.archives-ouvertes.fr) et constitué de deux app distinctes:
  - __elasticHal__, qui est chargé de récupérer les données des laboratoires et chercheurs sur HAL afin de les incorporer à une base de données Elastic
  - __sovisuhal__, qui est chargé d'afficher les données aux utilisateurs et se basant sur un environnement Django et les données récupérées puis stockées dans Elastic par elasticHal