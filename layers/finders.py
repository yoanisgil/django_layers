import os

from django.contrib.staticfiles.finders import BaseFinder
from django.contrib.staticfiles.storage import AppStaticStorage
from django.contrib.staticfiles import utils
from django.utils.datastructures import SortedDict
from django.utils.importlib import import_module

from django.conf import settings

from .middleware import get_current_request, get_active_layer
from .providers import BaseLayerProvider


class LayerStaticStorage(AppStaticStorage):
    def __init__(self, app, layer, *args, **kwargs):
        """
        Returns a static file storage if available in the given app.
        """
        # app is the actual app module
        self.layer = layer
        mod = import_module(app)
        mod_path = os.path.dirname(mod.__file__)
        location = os.path.join(mod_path, "layers", layer, 'static')
        super(AppStaticStorage, self).__init__(location, *args, **kwargs)


class AppLayerFinder(BaseFinder):
    storage_class = LayerStaticStorage

    @staticmethod
    def get_apps():
        if not hasattr(settings, 'LAYERED_APPS'):
            apps = settings.INSTALLED_APPS
        else:
            apps = getattr(settings, 'LAYERED_APPS')

            for app in apps:
                if not app in settings.INSTALLED_APPS:
                    raise Exception("Application %s not listed in INSTALLED_APPS" % app)

        excluded_apps = getattr(settings, 'EXCLUDE_FROM_LAYERS', [])

        return [app for app in apps if not app in excluded_apps]

    def __init__(self, apps=None, *args, **kwargs):
        provider_path = getattr(settings, "LAYERS_PROVIDER", "layers.providers.DefaultLayerProvider")

        if provider_path is None:
            raise Exception("This finder requires the LAYER_PROVIDER variable to be set in the "
                            "application's setting file")

        module_path, class_name = provider_path.rsplit('.', 1)
        module = import_module(module_path)

        provider_cls = getattr(module, class_name)

        if not issubclass(provider_cls, BaseLayerProvider):
            raise Exception("%s must be a descendant from layers.providers.BaseLayerProvider" % provider_cls)

        self.provider = provider_cls()
        self.layers = {}
        self.storages = SortedDict()

        if apps is None:
            self.apps = AppLayerFinder.get_apps()
        else:
            self.apps = apps

        self.update_storage()

        super(AppLayerFinder, self).__init__(*args, **kwargs)

    def update_storage(self):
        layers = self.provider.get_layers()

        for app in self.apps:
            for layer in layers.keys():
                if not layer in self.layers:
                    app_storage = self.storage_class(app, layer)

                    if os.path.isdir(app_storage.location):
                        if not app in self.storages:
                            self.storages[app] = {}

                        self.storages[app][layer] = app_storage

        # Remove from storage layers which are not longer present
        for layer in self.layers.keys():
            if not layer in layers:
                for app in self.apps:
                    if app in self.storages and layer in self.storages[app]:
                        del self.storages[app][layer]

                del self.layers[layer]

        # Update the list of layers
        self.layers.update(layers)

    def find(self, path, all=False, layer=None):
        """
        Looks for files in the app directories.
        """
        self.update_storage()

        matches = []
        for app in self.apps:
            match = self.find_in_app(app, path, layer)
            if match:
                if not all:
                    return match
                matches.append(match)
        return matches

    def find_in_app(self, app, path, layer=None):
        layer = layer or get_active_layer(get_current_request())
        storage = self.storages.get(app, {}).get(layer, None)
        if storage:
            if layer:
                if storage.exists(path):
                    matched_path = storage.path(path)
                    if matched_path:
                        return matched_path

    def list(self, ignore_patterns, layer=None):
        """
        List all files in all app storages.
        """
        if not layer:
            return

        self.update_storage()

        for storage in self.storages.itervalues():
            layer_storage = storage.get(layer, None)
            if layer_storage and layer_storage.exists(''):
                for path in utils.get_files(layer_storage, ignore_patterns):
                    yield path, layer_storage

