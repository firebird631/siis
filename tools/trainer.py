# @date 2023-04-114
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Machine Learning / Trainer tools

import base64
import copy
import math
import random
import subprocess
import traceback
import uuid
from datetime import datetime
from importlib import import_module

from common.utils import truncate
from config import utils
from strategy.learning.trainer import Trainer
from tools.tool import Tool

from terminal.terminal import Terminal
from database.database import Database

from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.trainer')
error_logger = logging.getLogger('siis.tools.error.trainer')
traceback_logger = logging.getLogger('siis.tools.traceback.trainer')


class TrainerTool(Tool):
    """
    Intercept training/machine learning demands and manage sub-process for backtesting, optimizing and finally
    output results for the caller.

    @todo In case of some other watcher/market are used for a strategy need to prefetch them if --initial-fetch
    """

    @classmethod
    def alias(cls):
        return "train"

    @classmethod
    def help(cls):
        return ("Process a training for a specific strategy.",
                "Specify --profile, --learning, --from, --to, --timeframe",
                "Optional --initial-fetch to fetch data before training")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("trainer", options)

        self._watcher_service = None

        self._profile = None
        self._learning = None

        self._profile_config = None
        self._learning_config = None

        self._trainer_clazz = None
        self._results = []

    def check_options(self, options):
        if not options.get('profile'):
            Terminal.inst().error("Missing strategy profile")
            return False

        if not options.get('learning'):
            Terminal.inst().error("Missing strategy learning proxy file")
            return False

        if not options.get('from'):
            Terminal.inst().error("Missing from datetime parameters")
            return False

        if not options.get('to'):
            Terminal.inst().error("Missing to datetime parameters")
            return False

        if not options.get('timeframe'):
            Terminal.inst().error("Missing backtest timeframe parameters")
            return False

        Terminal.inst().message("Import profile...")

        self._profile_config = utils.load_config(options, "profiles/%s" % options['profile'])
        if not self._profile_config:
            Terminal.inst().error("Miss-configured strategy profile file")
            return False

        Terminal.inst().message("Import learning...")

        self._learning_config = utils.load_learning(options, options['learning'])
        if not self._profile_config:
            Terminal.inst().error("Miss-configured learning proxy file")
            return False

        self._profile = options['profile']
        self._learning = options['learning']

        return True

    def init(self, options):
        # trainers
        trainers_config = utils.load_config(options, 'trainers')

        trainer_name = self._learning_config.get('trainer', {}).get('name')
        if not trainer_name:
            return False

        trainer = trainers_config.get(trainer_name)
        if not trainer:
            Terminal.inst().error("Cannot find trainer %s" % trainer_name)
            return False

        if trainer.get("status") is not None and trainer.get("status") == "load":
            # retrieve the class-name and instantiate it
            parts = trainer.get('classpath').split('.')

            try:
                module = import_module('.'.join(parts[:-1]))
                Clazz = getattr(module, parts[-1])
            except Exception as e:
                traceback_logger.error(traceback.format_exc())
                return False

            if not Clazz:
                Terminal.inst().error("Cannot load trainer %s" % trainer_name)
                return False

            self._trainer_clazz = Clazz

        # database manager
        Database.create(options)
        Database.inst().setup(options)

        # want speedup the database inserts
        Database.inst().enable_fetch_mode()

        return True

    def run(self, options):
        if 'initial-fetch' in options:
            Terminal.inst().info("Starting watcher's service...")
            self._watcher_service = WatcherService(None, options)

            watchers_config = self._profile_config.get('watchers', {})
            self._learning_config.get('watchers')

            for watcher_name, watcher_config in watchers_config.items():
                if watcher_name in self._learning_config.get('watchers'):
                    learning_watcher = self._learning_config.get('watchers')[watcher_name]

                    if 'symbols' in learning_watcher:
                        # overrides symbols
                        watcher_config['symbols'] = learning_watcher['symbols']

                markets = watcher_config.get('symbols', [])

                Terminal.inst().info("Create watcher %s to fetch initial markets data..." % watcher_name)
                watcher = self._watcher_service.create_watcher(options, watcher_name, markets)
                if watcher:
                    watcher.initial_fetch = True
                    watcher.connect()

                    markets = watcher.matching_symbols_set(markets, watcher.available_instruments())

                    for market_id in markets:
                        Terminal.inst().info("Fetch data for market %s..." % market_id)
                        watcher._watched_instruments.add(market_id)

                        try:
                            watcher.update_markets_info()
                            # @todo prefetch
                        except Exception as e:
                            error_logger.error(str(e))

                    watcher.disconnect()

        #
        # options for trainer
        #

        from_dt = options.get('from')
        to_dt = options.get('to')
        timeframe = options.get('timeframe')

        def gen_trainer_filename() -> str:
            return "trainer_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace(
                '/', '_').replace('+', '0')

        def read_trainer_file(filename: str):
            trainer_results = utils.load_learning(options, filename)

            if 'revision' in trainer_results:
                return trainer_results

            # not completed
            return None

        def fill_linked_parameters(learning_parameters: dict):
            org_strategy_params = self._learning_config.get('strategy', {}).get('parameters', {})
            trainer_strategy_params = learning_parameters.get('strategy', {}).get('parameters', {})

            for pname, pvalue in org_strategy_params.items():
                if 'linked' in pvalue and pvalue['linked']:
                    for linked in pvalue['linked']:
                        trainer_strategy_params[linked] = trainer_strategy_params[pname]

        # instantiate trainer and process it
        trainer_commander = self._trainer_clazz.create_commander(self._profile,
                                                                 self._profile_config,
                                                                 self._learning_config)

        def start_trainer(learning_parameters: dict, profile_name: str):
            learning_filename = gen_trainer_filename()

            # lookup for linked parameters
            fill_linked_parameters(learning_parameters)

            utils.write_learning(options['learning-path'], learning_filename, learning_parameters)

            cmd_opts = [
                'python',
                'siis.py',
                options['identity'],
                '--profile=%s' % profile_name,
                '--backtest',
                '--from=%s' % from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                '--to=%s' % to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                '--timeframe=%s' % timeframe,
                '--learning=%s' % learning_filename,
                '--no-interactive'
            ]

            trainer_result = None
            fitness = 0.0

            Terminal.inst().info("Run sub-process %s" % learning_filename)
            with subprocess.Popen(cmd_opts, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL) as p:
                stdout, stderr = p.communicate()
                # if stdout:
                #     print(stdout.decode())

                trainer_result = read_trainer_file(learning_filename)
                if trainer_result:
                    Terminal.inst().info("-- %s trainer success with %s" % (
                        learning_filename, trainer_result.get('performance', "0.00%")))
                    print(trainer_result)

                    perf = float(trainer_result.get('performance', "0.00%").rstrip('%'))

                    # @todo adjust by MDD ..
                    fitness = perf * 0.01
                else:
                    Terminal.inst().info("-- %s trainer failed" % learning_filename)

                utils.delete_learning(options['learning-path'], learning_filename)

            return fitness, trainer_result

        trainer_commander.start(start_trainer)
        res = trainer_commander.results
        for r in res:
            logger.debug(r)

        # complete
        better_trainer_result = None
        final_learning_config = copy.deepcopy(self._learning_config)
        max_perf = 0.0
        better = -1

        try:
            min_perf = float(self._learning_config.get('trainer', {}).get('min-performance', "0.00%").rstrip('%'))
        except ValueError:
            min_perf = 0.0

        for i, result in enumerate(self._results):
            try:
                performance = float(result.get('performance', "0.00%").rstrip('%'))
            except ValueError:
                continue

            if performance >= min_perf and performance > max_perf:
                max_perf = performance
                better = i

        if better >= 0:
            better_trainer_result = self._results[better]

        if better_trainer_result:
            # utils.merge_learning_config(final_learning_config, better_trainer_result)
            final_learning_config = better_trainer_result  # @todo
            utils.write_learning(options, self._learning, final_learning_config)

        return True

    def terminate(self, options):
        if self._watcher_service:
            self._watcher_service.terminate()

        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = TrainerTool
