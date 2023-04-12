# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Config parser

import json
import itertools
import os
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
    _identities = {}

    user_file = pathlib.Path(config_path, 'identities.json')
    if user_file.exists():
        try:
            with open(str(user_file), 'r') as f:
                _identities = json.load(f)
        except Exception as e:
            error_logger.error("During parsing of %s %s" % (config_path, repr(e)))

    return _identities


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
            error_logger.error("During parsing of %s : %s" % (user_file, repr(e)))

    return merge_parameters(default_config, user_config)


def load_learning(options, attr_name):
    if not attr_name:
        return {}

    learning_path = options['learning-path'] if (type(options) is dict and 'learning-path' in options) else options

    user_file = pathlib.Path(learning_path, attr_name + '.json')
    if user_file.exists():
        try:
            with open(str(user_file), 'r') as f:
                user_config = json.load(f)
        except Exception as e:
            error_logger.error("%s %s%s" % (repr(e), attr_name, '.json'))
            error_logger.error("During parsing of %s : %s" % (user_file, repr(e)))

        return user_config

    return {}


def write_learning(options, attr_name, data):
    if not attr_name:
        return

    learning_path = options['learning-path'] if (type(options) is dict and 'learning-path' in options) else options

    user_file = pathlib.Path(learning_path, attr_name + '.json')
    try:
        dump = json.dumps(data, indent=4)

        with open(str(user_file), 'wb') as f:
            f.write(dump.encode('utf-8'))

    except Exception as e:
        error_logger.error("%s %s%s" % (repr(e), attr_name, '.json'))
        error_logger.error("During writing of %s : %s" % (user_file, repr(e)))


def delete_learning(options, attr_name):
    if not attr_name:
        return

    learning_path = options['learning-path'] if (type(options) is dict and 'learning-path' in options) else options

    user_file = pathlib.Path(learning_path, attr_name + '.json')
    os.remove(str(user_file))


def merge_learning_config(parameters, learning_config):
    strategy_params = learning_config.get('strategy', {}).get('parameters', {})

    def extract_from_dictionary(dictionary, keys_or_indexes):
        _value = dictionary

        try:
            for key_or_index in keys_or_indexes:
                if type(_value) is dict:
                    _value = _value[key_or_index]
                elif type(_value) in (list, tuple):
                    _value = _value[int(key_or_index)]
            return True, _value

        except TypeError:
            return False, None

    def set_to_dictionary(dictionary, l_new_value, keys_or_indexes):
        _value = dictionary

        try:
            for i, key_or_index in enumerate(keys_or_indexes):
                if i == len(keys_or_indexes) - 1:
                    if type(_value) is dict:
                        _value[key_or_index] = l_new_value
                    elif type(_value) in (list, tuple):
                        _value[int(key_or_index)] = l_new_value

                    return

                if type(_value) is dict:
                    _value = _value[key_or_index]
                elif type(_value) in (list, tuple):
                    _value = _value[int(key_or_index)]

        except TypeError:
            pass

    for path, new_value in strategy_params.items():
        split_path = path.split('.')

        if not split_path:
            continue

        found, value = extract_from_dictionary(parameters, split_path)

        if found:
            set_to_dictionary(parameters, new_value, split_path)
