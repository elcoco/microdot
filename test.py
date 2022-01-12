#!/usr/bin/env python3

import logging

from types import SimpleNamespace

logger = logging.getLogger('microdot')


class NestedNamespace(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        self.__dict__['_dict'] = dictionary
        self.update(self._dict)

    def update(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                super().__setattr__(key, NestedNamespace(value))
            else:
                super().__setattr__(key, value)

    def __setattr__(self, key, value):
        self.__dict__['_dict'][key] = value
        self.update(self._dict)



d = {}
d['a'] = {}
d['a']['banaan'] = 'qqqqqq'
d['a']['disko'] = {}
d['a']['disko']['bever'] = 'aaaaaaaa'
d['a']['disko']['bever2'] = 'bbbbbb'
d['b'] = {}
d['c'] = {}


nd = NestedNamespace(d)
print(nd.a.banaan)
print(nd.a.disko)
nd.a = {}
nd.a.bever = 'kljk'

print(nd.a.bever)


