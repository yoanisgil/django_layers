from django.conf import settings
from django.db import models
from django.db.models import FieldDoesNotExist
from django.utils.importlib import import_module
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

class BaseLayerProvider(object):
    """
    Base class for all layers providers. A provider is an object which is capable of loading a dictionary of
    available layers.
    """
    def __init__(self):
        pass

    def get_layers(self):
        raise NotImplemented


class DefaultLayerProvider(BaseLayerProvider):
    """
    Layer provider used by default. This provider retrieves the dictionary of available layers from the app's setting
    file.
    """
    def __init__(self):
        super(BaseLayerProvider, self).__init__()

    def get_layers(self):
        layers = getattr(settings, 'LAYERS', {})

        return layers


class ModelLayerProvider(BaseLayerProvider):
    SETTINGS_ENTRY = "LAYERS_MODEL_PROVIDER_CONFIG"
    MODEL_KEY = 'model'
    LAYER_NAME_FIELD_KEY = 'layer_name_field'
    PATH_URL_BUILDER_KEY = 'path_url_builder'
    QUERY_FILTER_KEY = 'query_filter_key'

    def __init__(self):
        layer_settings = getattr(settings, ModelLayerProvider.SETTINGS_ENTRY)

        if layer_settings is None:
            raise Exception("%s requires the property %s to be set in the application's settings file" %
                            (ModelLayerProvider.__name__, ModelLayerProvider.SETTINGS_ENTRY))

        model_cls = layer_settings.get(ModelLayerProvider.MODEL_KEY, None)

        if model_cls is None:
            raise Exception("The %s entry is required in the %s dictionary" % (ModelLayerProvider.MODEL_KEY,
                                                                               ModelLayerProvider.SETTINGS_ENTRY))

        layer_name_field = layer_settings.get(ModelLayerProvider.LAYER_NAME_FIELD_KEY, None)

        if layer_name_field is None:
            raise Exception("The %s entry is required in the %s dictionary" % (ModelLayerProvider.LAYER_NAME_FIELD_KEY,
                                                                               ModelLayerProvider.SETTINGS_ENTRY))

        module_path, class_name = model_cls.rsplit('.', 1)
        module = import_module(module_path)

        model = getattr(module, class_name)

        if not issubclass(model, models.Model):
            raise Exception("model must be a descendant from models.Model")
        try:
            model._meta.get_field_by_name(layer_name_field)
        except FieldDoesNotExist:
            raise Exception("%s field is not an attribute from the provided model" % layer_name_field)

        self.model = model
        self.layer_name_field = layer_name_field
        self.path_url_builder = layer_settings.get(ModelLayerProvider.PATH_URL_BUILDER_KEY,
                                                   lambda name: "%s/%s" % (getattr(settings, 'STATIC_ROOT'), name))
        self.query_filter = layer_settings.get(ModelLayerProvider.QUERY_FILTER_KEY, None)
        self.layers = None

        post_save.connect(self.on_post_save, sender=model)
        post_delete.connect(self.on_post_delete, sender=model)

    def on_post_save(self, sender, **kwargs):
        if 'instance' in kwargs:
            instance = kwargs.get('instance')
            layer_name = getattr(instance, self.layer_name_field)

            if layer_name and not layer_name in self.layers:
                self.layers.update({layer_name: self.path_url_builder(layer_name)})

    def on_post_delete(self, sender, **kwargs):
        if 'instance' in kwargs:
            instance = kwargs.get('instance')
            layer_name = getattr(instance, self.layer_name_field)

            if layer_name and layer_name in self.layers:
                del self.layers[layer_name]

    def get_layers(self):
        if self.layers is None:
            if self.query_filter:
                objects = self.model.objects.filter(self.query_filter)
            else:
                objects = self.model.objects.all()

            self.layers = {}

            for obj in objects:
                layer_name = getattr(obj, self.layer_name_field)
                if layer_name:
                    self.layers.update({layer_name: self.path_url_builder(layer_name)})

        return self.layers