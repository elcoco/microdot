#!/usr/bin/env python3

# for config file format
import yaml
import os, sys
import logging

from types import SimpleNamespace

logger = logging.getLogger('microdot')

class ConfigException(Exception): pass


class NestedNamespace(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        for key, value in dictionary.items():
            if isinstance(value, dict):
                self.__setattr__(key, NestedNamespace(value))
            else:
                self.__setattr__(key, value)


class Config(dict):
    def __init__(self, path=False):
        self._config_path = path
        self._config = {}

        if not path:
            configdir = os.path.expanduser('~') + '/.config/' + os.path.basename(sys.argv[0]).split(".")[0]
            self._config_path = configdir + '/' + os.path.basename(sys.argv[0]).split(".")[0] + '.yaml'

    def __str__(self):
        return str(self._config)

    def __bool__(self):
        # is called when object is tested with: if <object> == True
        if len(self._config) > 0:
            return True
        else:
            return False

    def __getitem__(self, key):
        try:
            return self._config[key]
        except KeyError as e:
            raise KeyError(f"Key doesn't exist, key={key}")

    def __setitem__(self, key, value):
        try:
            self._config[key] = value
        except KeyError as e:
            logger.warning(f"Failed to set key, Key doesn't exist, key={key}")

    def set_path(self, path):
        self._config_path = path

    def set_config_data(self, data):
        self._config = data

    def keys(self):
        # override dict keys method
        return self._config.keys()

    def dict_deep_merge(self, d1, d2):
        """ deep merge two dicts """
        dm = d1.copy()
        for k,v in d2.items():
            if k in dm.keys() and type(v) == dict:
                dm[k] = self.dict_deep_merge(dm[k], d2[k])
            else:
                dm[k] = v
        return dm

    def test_file(self, path):
        """ Test if file exists """
        try:
            with open(path) as f:
                return True
        except IOError as e:
            return False

    def ensure_dir(self, dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
            logger.info(f"Created directory: {dirname}")

    def configfile_exists(self):
        return self.test_file(self._config_path)

    def load(self, path=False, merge=True):
        if not path:
            path = self._config_path

        try:
            with open(path, 'r') as configfile:
                cfg = yaml.safe_load(configfile)

                if not cfg:
                    return

                if merge:
                    self._config = self.dict_deep_merge(self._config, cfg)
                else:
                    self._config = cfg

                logger.info(f"Loaded config file, path={path}")
            return True
        except yaml.YAMLError as e:
            raise ConfigException(f"Failed to load YAML in config file: {path}\n{e}")
        except FileNotFoundError as e:
            raise ConfigException(f"Config file doesn't exist: {path}\n{e}")

    def write(self, path=False, commented=False):
        if not path:
            path = self._config_path

        self.ensure_dir(os.path.dirname(path))

        with open(path, 'w') as outfile:
            try:
                yaml.dump(self._config, outfile, default_flow_style=False)
                logger.info(f"Wrote config to: {path}")
            except yaml.YAMLError as e:
                raise ConfigException(f"Failed to write YAML in config file: {path}, message={e}")

        # comment the config file that was just written by libYAML
        if commented:
            lines = []

            with open(self._config_path, 'r') as f:
                lines = f.readlines()

            lines = [f"#{x}" for x in lines]

            with open(self._config_path, 'w') as f:
                f.writelines(lines)


