# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Config parser

import copy
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
            d.update({key: merge(a.get(key, None), b[key]) for key in b if key not in ('timeframes', 'contexts')})
            return d

        if isinstance(a, list) and isinstance(b, list):
            return [merge(x, y) for x, y in itertools.zip_longest(a, b)]

        return a if b is None else b

    final_params = merge(default, user)

    if 'timeframes' in default or 'timeframes' in user:
        # special case for timeframes and contexts
        default_timeframes = default.get('timeframes', {})
        user_timeframes = user.get('timeframes', {})
        final_timeframes = {}

        for _k, _b in user_timeframes.items():
            if _k not in default_timeframes:
                # original from user
                final_timeframes[_k] = copy.deepcopy(_b)
            else:
                # update from default
                # _a = default_timeframes[_k]
                # final_timeframes[_k] = merge(_a, _b)
                # take user version
                final_timeframes[_k] = copy.deepcopy(_b)

        final_params['timeframes'] = final_timeframes
        # logger.debug(final_params['timeframes'])

    if 'contexts' in default or 'contexts' in user:
        default_contexts = default.get('contexts', {})
        user_contexts = user.get('contexts', {})
        final_contexts = {}

        for _k, _b in user_contexts.items():
            if _k not in default_contexts:
                # original from user
                final_contexts[_k] = copy.deepcopy(_b)
            else:
                # update from default
                # _a = default_contexts[_k]
                # final_contexts[_k] = merge(_a, _b)
                # take user version
                final_contexts[_k] = copy.deepcopy(_b)

        final_params['contexts'] = final_contexts
        # logger.debug(final_params['contexts'])

    return final_params


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
