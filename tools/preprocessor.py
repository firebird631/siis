# @date 2020-11-05
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Preprocessor tools

import sys
import logging
import traceback

from tools.tool import Tool
    
from terminal.terminal import Terminal
from database.database import Database

from strategy.strategy import Strategy
from strategy.service import StrategyService

import logging
logger = logging.getLogger('siis.tools.preprocessor')
error_logger = logging.getLogger('siis.tools.error.preprocessor')
traceback_logger = logging.getLogger('siis.tools.traceback.preprocessor')


class Preprocessor(Tool):
    """
    Preprocess cache of data for a strategy with conditions.
    """ 

    @classmethod
    def alias(cls):
        return "preprocess"

    @classmethod
    def help(cls):
        return ("Pre-process strategy cache of one or many markets and a specific broker.",
                "Specify --profile, --broker, --market.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("preprocessor", options)

        self._strategies = {}
        self._indicators = {}

        self._profile = options.get('profile', 'default')

        self._indicators_config = utils.load_config(options, 'indicators')
        self._strategies_config = utils.load_config(options, 'strategies')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        self._from_date = options.get('from')  # UTC tz
        self._to_date = options.get('to')  # UTC tz
        self._timestep = options.get('timestep', 60.0)
        self._timeframe = options.get('timeframe', 0.0)

        self._strategy = None

    def check_options(self, options):
        if options.get('profile') and options.get('market') and options.get('broker'):
            return True

        return False

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

        # want speedup the database inserts
        Database.inst().enable_fetch_mode()

        self.setup()

        return True

    def run(self, options):
        Terminal.inst().info("Starting strategy's service...")
        self._strategy_service = StrategyService(options)

        markets = options['market'].split(',')

        for market_id in markets:
            preprocessor = self.create_strategy() self._strategy_service.create_preprocessor(options, options['broker'], market_id)

            if preprocessor:
                logger.info("Pre-process market %s..." % (market_id,))

                try:
                    while not preprocessor.finished():
                        preprocessor.process(15*60)
                except Exception as e:
                    logger.error("Exception during pre-processing of market %s : %s !" % (market_id, repr(e)))
                    traceback_logger.error(traceback.format_exc())
            else:
                logger.error("Market %s not found !" % (market_id,))

        return True

    def terminate(self, options):
        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True

    def setup(self):
        # indicators
        for k, indicator in self._indicators_config.items():
            if indicator.get("status") is not None and indicator.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = indicator.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise Exception("Cannot load indicator %s" % k) 

                self._indicators[k] = Clazz

        # strategies
        for k, strategy in self._strategies_config.items():
            if k == "default":
                continue

            if strategy.get("status") is not None and strategy.get("status") == "load":
                # retrieve the classname and instanciate it
                parts = strategy.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])

                if not Clazz:
                    raise Exception("Cannot load strategy %s" % k)

                self._strategies[k] = Clazz

    def create_preprocessor(self):
        # and finally strategy
        strategy_profile = self._profile_config.get('strategy')
        if not strategy_profile or strategy_profile.get('name', "") == "default":
            return

        # overrided strategy parameters
        parameters = strategy_profile.get('parameters', {})

        if not strategy_profile or not strategy_profile.get('name'):
            error_logger.error("Invalid strategy configuration for strategy %s. Ignored !" % strategy_profile['name'])

        Clazz = self._strategies.get(strategy_profile['name'])
        if not Clazz:
            error_logger.error("Unknown strategy name %s. Ignored !" % strategy_profile['name'])
            return

        strategy_inst = Clazz(self, None, None, self._profile_config, parameters)
        strategy_inst.set_identifier(strategy_profile.get('id', strategy_profile['name']))

        return strategy_inst

    def preprocess(self, broker, market):
        pass

tool = Preprocessor
