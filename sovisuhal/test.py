from django.shortcuts import render, redirect
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
import json
from . import forms
from django.views.decorators.clickjacking import xframe_options_exempt

from django.core.mail import mail_admins, send_mail
from .forms import ContactForm
from decouple import config
from django.contrib import messages
#from ssl import create_default_context
#from elasticsearch.connection import create_ssl_context
from uniauth.decorators import login_required

Mode = config ('mode')

struct = "198307662"

def esConnector(mode = Mode):
    if mode == "Prod":

        secret = config ('ELASTIC_PASSWORD')
        # context = create_ssl_context(cafile="../../stackELK/secrets/certs/ca/ca.crt")
        es = Elasticsearch('localhost',
                           http_auth=('elastic', secret),
                           scheme="http",
                           port=9200,
                           # ssl_context=context,
                           timeout=10)
    else:
        es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
    return es

es = esConnector()
scope_param = {
    "query": {
        "match_all": {}
    }
}
count = es.count(index=struct +"*-researchers", body=scope_param)['count']
scope_param = {
    "query": {
        "match": {
            "labHalId": id
        }
    }
}


res = es.search(index=struct +"*-researchers", body=scope_param, size=count)
entities = res['hits']['hits']