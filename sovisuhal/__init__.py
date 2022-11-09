from __future__ import absolute_import, unicode_literals
from elasticHal.celery import app as celery_app
if __name__ == '__main__':
    __all__ = ('celery_app',)
