# Docker-Compose SoVisu

## Généralités 
Suite de services indispensables ou pas pour l'application SoVisu. 
Le docker-compose met en œuvre :
### Services indispensables
- Elasticsearch (port 9200). Composant d'indexation. Mode Cluster dans cette version.
- Kibana (port 5601). Gestion des index, gestions de tableaux de bord
Non fait : nginx; grafa et cerebro
- Nginx en reverse proxy https sur les différents ports via un chemin dédié (/kibana ; /cerebro et /grafana)

### Services de monitoring
- Filebeat (transforme les fichiers logs en json, flux vers Elastic)

- MetricBeat (calcule des agrégations de métriques synthétiques sur notamment les logs) ou les flux issus de docker

- logstash est en "attente" car trop gourmand en mémoire.

### Services de Visualisation
- *grafana* : surcouche/alternative à *Kibana*, spécialisée dans les graphes de séries temporelle (suivi des CPU, mémoire, etc.). Note : un tableau de bord de ce type est déjà présent dans *Kibana*. Esthétique et UX priment, j'ai conservé *grafana*.
- *cerebro* : utilitaire de vue synthétique sur ES. Produit des indicateurs et métriques très simples.

## Notes d'installation
### Arborescence
Chacun des services dispose de son répertoire qui contient : 

- les fichiers de configurations de chacun (*.yaml, .ini* ou.*conf*)
- les fichiers de sécurité (*.keystore*) sont dans le dossier "*secret*" pour *beat* et dans leurs dossiers respectifs pour *elasticsearch* et *kibana*.

### Description
Le docker-compose actuel intègre :
1. la mise en place d'une sécurité renforcée via :
- les variables d'environnement
- séparation des configurations (fichiers *yml*) de chacun des services et de leurs différents modules.

2. la séparation d'une zone de stockage "hors docker" par le montage de volumes. ES est en parallèle à ce dossier alors que la base *grafana* est dans son propre dossier.


## Lancement

Créer un dossier vide DATA dans ce dossier (stackELK)

En l'état : `docker-compose up -d`
La machine actuelle ne redémarre actuellement QUE le service *nginx* (et je sais même plus comment j'ai fait).

### Premier lancement
- modifier le compose en supprimant les liens vers les keystores. 
- démarrez Elastic pour lancer l'utilitaire de [création de mots de passe](https://www.elastic.co/guide/en/elasticsearch/reference/current/setup-passwords.html)
- démarrez-les *filebeat, metricbeat* pour générer leur keystore (avec les mdp précédents) et les stocker 'hors container' (docker cp container:/usr/share/data/keystore /secret/service) (par ex.). Modifiez aussi le fichier .env en conséquence.
- adaptez les clés SSL de la machine pour les rendre disponible à nginx (dossier secret/ssl).
- croisez les doigts 

Note : le shell est accessible sur un container via :
docker exec -ti container /bin/bash


### Tableaux de bord kibana
L'accès à la zone monitoring de Kibana ou de grafana permettra de suivre : 
- la consommation de ressources (CPU, mémoire, réseau, disque) ;
- l'activité des différentes machines (services ci-dessus)
- le trafic web

Il faudra probablement installer les différents tableaux de bord filebeat et metricbeat. filebeat setup --dashboards 

## Compléments

- en plus des différentes adaptations sur la MV sont à noter :
1. filebeat est configuré pour envoyer les logs nginx à elastic
2. metricbeat intègre les flux de logs dockers et les métriques système

Note : déport des logs sur loki (docker plugin install grafana/loki-docker-driver :latest --alias loki --grant-all-permissions)... alors que non utilisé. Il parait que ce serait moins gourmand en ressources que filebeat et metricbeat.


