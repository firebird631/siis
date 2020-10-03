# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Config parser

import json
import importlib.util
import itertools
import pathlib

import logging
logger = logging.getLogger('siis.config')
error_logger = logging.getLogger('siis.error.config')


def merge_parameters(default, user):
    def merge(a, b):
        if a is not None and b is None:
            return None

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

    user_file = pathlib.Path(config_path, 'identities.json')
    if user_file.exists():
        try:
            with open(str(user_file), 'r') as f:
                identities = json.load(f)
        except Exception as e:
            error_logger.error("During parsing of %s %s" % (config_path, repr(e)))

    return identities


def load_config(options, attr_name):
    default_config = {}

    default_file = pathlib.Path(options['working-path'], 'config', attr_name + '.json')
    if default_file.exists():
        try:
            with open(str(default_file), 'r') as f:
                default_config = json.load(f)
        except Exception as e:
            error_logger.error("During parsing of %s %s" % (default_file, repr(e)))

    user_config = {}

    user_file = pathlib.Path(options['config-path'], attr_name + '.json')
    if user_file.exists():
        try:
            with open(str(user_file), 'r') as f:
                user_config = json.load(f)
        except Exception as e:
            error_logger.error("%s %s%s" % (repr(e), attr_name, '.json'))
            error_logger.error("During parsing of %s" % (user_file, repr(e)))

    return merge_parameters(default_config, user_config)
