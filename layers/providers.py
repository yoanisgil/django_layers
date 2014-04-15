from django.conf import settings


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