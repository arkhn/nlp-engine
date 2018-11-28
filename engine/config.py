import os
import yaml


class ConfigNode:
    def __init__(self, node):
        self._dict = {}
        for k, v in node.items():
            if not isinstance(v, (int, float, str)) and v is not None:
                v = ConfigNode(v)
            setattr(self, k, v)
            self._dict[k] = v

    def to_dict(self):
        return self._dict


class Config:
    def __init__(self, key=None):
        self._dict = {}
        self._config = {}
        path = os.path.dirname(__file__)
        filename = "./config.yml"
        with open(os.path.join(path, filename)) as config_file:
            config = yaml.safe_load(config_file)
            if key is not None:
                config = config[key]
            self._config = config

        for attr, node in self._config.items():
            if not isinstance(node, (int, float, str)) and node is not None:
                node = ConfigNode(node)
            setattr(self, attr, node)
            self._dict[attr] = node

    def to_dict(self):
        return self._dict
