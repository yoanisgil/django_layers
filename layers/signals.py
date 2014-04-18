__author__ = 'Yoanis Gil'

import django.dispatch

layer_added = django.dispatch.Signal(providing_args=["layer_name"])
layer_removed = django.dispatch.Signal(providing_args=["layer_name"])
