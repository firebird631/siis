# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# 

import importlib.util

import logging
logger = logging.getLogger('siis.config')


def identities(config_path):
	spec = importlib.util.spec_from_file_location("config.identity", '/'.join((config_path, 'identity.py')))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod.IDENTITIES if hasattr(mod, 'IDENTITIES') else {}


def watchers(config_path):
	from config import config
	default_config = config.WATCHERS or {}

	res = {}
	try:
		spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		if hasattr(mod, 'WATCHERS'):
			return mod.WATCHERS
	except FileNotFoundError:
		pass
	except Exception as e:
		logger.error(repr(e))

	return default_config


def fetchers(config_path):
	from config import config
	default_config = config.FETCHERS or {}

	res = {}
	try:
		spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		if hasattr(mod, 'FETCHERS'):
			return mod.FETCHERS
	except FileNotFoundError:
		pass
	except Exception as e:
		logger.error(repr(e))

	return default_config


def traders(config_path):
	from config import config
	default_config = config.TRADERS or {}

	res = {}
	try:
		spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		if hasattr(mod, 'TRADERS'):
			return mod.TRADERS
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


def monitoring(config_path):
	from config import config
	default_config = config.MONITORING or {}

	res = {}
	try:
		spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		if hasattr(mod, 'MONITORING'):
			return mod.MONITORING
	except FileNotFoundError:
		pass
	except Exception as e:
		logger.error(repr(e))

	return default_config


def databases(config_path):
	from config import config
	default_config = config.DATABASES or {}

	res = {}
	try:
		spec = importlib.util.spec_from_file_location(".", '/'.join((config_path, 'config.py')))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		if hasattr(mod, 'DATABASES'):
			return mod.DATABASES
	except FileNotFoundError:
		pass
	except Exception as e:
		logger.error(repr(e))

	return default_config
