#!/usr/bin/env python3

# for config file format
import yaml
import os, sys
import logging
from pprint import pprint
from pathlib import Path

from types import SimpleNamespace

logger = logging.getLogger('microdot')

class ConfigException(Exception): pass

class NestedNamespace(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        self.__dict__['_config'] = dictionary
        self.update(self._config)

    def update(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                super().__setattr__(key, NestedNamespace(value))
            else:
                super().__setattr__(key, value)

    def __setattr__(self, key, value):
        self.__dict__['_config'][key] = value
        self.update(self._config)


class Config(NestedNamespace):
    def __init__(self, path=None, **kwargs):
        super().__init__({}, **kwargs)

        # we can't directly assign because that would trigger __setattr__
        if path:
            self.__dict__['_config_path'] = path
        else:
            self.__dict__['_config_path'] = (Path.home() / '.config' / Path(__file__).name).with_suffix('') / 'config.yaml'

    def set_path(self, path):
        self.__dict__['_config_path'] = path

    def configfile_exists(self):
        return self._config_path.is_file()

    def dict_deep_merge(self, d1, d2):
        """ deep merge two dicts """
        dm = d1.copy()
        for k,v in d2.items():
            if k in dm.keys() and type(v) == dict:
                dm[k] = self.dict_deep_merge(dm[k], d2[k])
            else:
                dm[k] = v
        return dm

    def load(self, path=False, merge=True):
        if not path:
            path = self._config_path

        try:
            with open(path, 'r') as configfile:
                cfg = yaml.safe_load(configfile)

                if not cfg:
                    return

                if merge:
                    self.__dict__['_config'] = self.dict_deep_merge(self._config, cfg)
                else:
                    self.__dict__['_config'] = cfg

                # update attributes
                self.update(self._config)

                logger.debug(f"Loaded config file, path={path}")
            return True
        except yaml.YAMLError as e:
            raise ConfigException(f"Failed to load YAML in config file: {path}\n{e}")
        except FileNotFoundError as e:
            raise ConfigException(f"Config file doesn't exist: {path}\n{e}")

    def write(self, path=False, commented=False):
        if not path:
            path = self._config_path

        if not path.parent.is_dir():
            path.parent.mkdir(parents=True)
            logger.info(f"Created directory: {path}")

        with open(path, 'w') as outfile:
            try:
                yaml.dump(self._config, outfile, default_flow_style=False)
                logger.info(f"Wrote config to: {path}")
            except yaml.YAMLError as e:
                raise ConfigException(f"Failed to write YAML in config file: {path}, message={e}")

        # comment the config file that was just written by libYAML
        if commented:
            lines = [f"#{x}" for x in path.read_text().split('\n')]
            path.write_text('\n'.join(lines))
