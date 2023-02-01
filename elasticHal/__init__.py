from __future__ import absolute_import, unicode_literals
from elasticHal.celery import app as celery_app
# je sais pas pourquopi passé à l'as dans le git pull
__all__ = ('celery_app',)
