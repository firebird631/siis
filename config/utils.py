# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# 

import json
import importlib.util
import itertools

import logging
logger = logging.getLogger('siis.config')
error_logger = logging.getLogger('siis.error.config')


def merge_parameters(default, user):
    def merge(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            d = dict(a)
            d.update({k: merge(a.get(k, None), b[k]) for k in b})
            return d

        if isinstance(a, list) and isinstance(b, list):
            return [merge(x, y) for x, y in itertools.zip_longest(a, b)]

        return a if b is None else b

    return merge(default, user)


def identities(config_path):
    """
    Get a dict containing any configured identities from user identity.json.
    """
    identities = {}

    try:
        with open('/'.join((config_path, 'identity.json')), 'r') as f:
            identities = json.load(f)
    except Exception as e:
        error_logger.error(repr(e))

    return identities


def attribute(config_path, attr_name):
    from config import config
    default_config = getattr(config, attr_name) or {}

    res = {}
    try:
        spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, attr_name):
            return merge_parameters(default_config, getattr(mod, attr_name))
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(repr(e))

    return default_config


def appliances(config_path):
    from config import appliance
    default_config = appliance.APPLIANCES or {}

    res = {}
    try:
        spec = importlib.util.spec_from_file_location("config.appliance", '/'.join((config_path, 'appliance.py')))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, 'APPLIANCES'):
            return mod.APPLIANCES
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(repr(e))

    return default_config


def profiles(config_path):
    from config import appliance
    default_config = appliance.PROFILES or {}

    res = {}
    try:
        spec = importlib.util.spec_from_file_location("config.appliance", '/'.join((config_path, 'appliance.py')))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, 'PROFILES'):
            return mod.PROFILES
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(repr(e))

    return default_config
