# @date 2023-04-114
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Machine Learning / Trainer tools

from __future__ import annotations

from typing import Union

import time
import base64
import copy
import subprocess
import traceback
import uuid

from importlib import import_module

from config import utils
from strategy.learning.trainer import TrainerJob
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

    @todo --initial-fetch must be implemented to retrieve/build necessary missing data
    @todo In case of some other watcher/market are used for a strategy need to prefetch them if --initial-fetch
    """

    @classmethod
    def alias(cls):
        return "train"

    @classmethod
    def help(cls):
        return ("Process a training for a specific strategy.",
                "Specify --profile, --learning, --from, --to, --timestep",
                "Optional --initial-fetch to fetch data before training",
                "Optional --parallels=<n> to parallelize many sub-process (default 1)")

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

        self._max_sub_process = 1
        self._trainer_commander = None

        self._process_times = []
        self._last_process_time = 0.0
        self._executed_jobs = 0
        self._last_progress = 0.0

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

        if not options.get('timestep'):
            Terminal.inst().error("Missing backtest timestep parameters")
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

        if "revision" in self._learning_config:
            Terminal.inst().error("This learning file is already computed")
            return False

        self._profile = options['profile']
        self._learning = options['learning']

        self._max_sub_process = options.get('parallel', 1)

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
        timestep = options.get('timestep')

        prev_progress = 0.0

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
        self._trainer_commander = self._trainer_clazz.create_commander(self._profile,
                                                                       self._profile_config,
                                                                       self._learning_config)

        if self._max_sub_process > 1:
            self._trainer_commander.set_parallel(self._max_sub_process)

        def start_trainer(learning_parameters: dict, profile_name: str, caller: Union[TrainerJob, None]):
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
                '--timestep=%s' % timestep,
                '--learning=%s' % learning_filename,
                '--no-interactive'
            ]

            trainer_result = None
            fitness = 0.0

            Terminal.inst().info("Run sub-process %s" % learning_filename)
            with subprocess.Popen(cmd_opts, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL) as process:

                initial_time = time.time()
                err = False

                if caller:
                    # assign related process
                    caller.process = process

                while 1:
                    code = process.poll()
                    if code is not None:
                        break

                    now = time.time()

                    if self._last_process_time and now - initial_time > 3.0 * self._last_process_time:
                        logger.error("Abnormal process %s duration kill" % learning_filename)
                        process.kill()

                    if self._last_process_time and now - initial_time > 1.5 * self._last_process_time and not err:
                        logger.warning("Abnormal process %s duration, wait a little before kill it" % learning_filename)
                        err = True

                    try:
                        stdout, stderr = process.communicate(timeout=0.1)
                        if stdout:
                            msg = stdout.decode()
                            if "error" in msg.lower():
                                # error during backtest kill
                                logger.debug(msg)
                                logger.error("Kill process %s error" % learning_filename)

                                process.kill()

                    except subprocess.TimeoutExpired:
                        pass

                # progress log
                progress = self._trainer_commander.progress()
                if progress - self._last_progress > 5.0:
                    Terminal.inst().info("Progress %.2f%%" % progress)
                    self._last_progress = progress

                # output result, stats...
                trainer_result = read_trainer_file(learning_filename)
                if trainer_result:
                    duration = time.time() - initial_time

                    if not self._last_process_time and duration:
                        remain_duration_est = self._trainer_commander.estimate_duration(duration)
                        Terminal.inst().info("Estimate total duration to %.2f minutes" % (remain_duration_est / 60,))

                    self._last_process_time = duration

                    Terminal.inst().info("-- %s trainer success with %s" % (
                        learning_filename, trainer_result.get('performance', "0.00%")))
                    # print(trainer_result.get('strategy').get('parameters'))

                    perf = float(trainer_result.get('performance', "0.00%").rstrip('%'))

                    # @todo adjust by MDD ..
                    fitness = -perf
                else:
                    Terminal.inst().info("-- %s trainer failed" % learning_filename)

                utils.delete_learning(options['learning-path'], learning_filename)

            return fitness, trainer_result

        # run training
        self._trainer_commander.start(start_trainer)

        # get final better results, compare, select one
        best_result = self._trainer_commander.evaluate_best()

        final_learning_config = copy.deepcopy(self._learning_config)

        if best_result:
            # found best result
            logger.info("Best candidate found !")
            logger.info(best_result)

            # merge strategy parameters
            best_result_strategy_parameters = best_result.get('strategy', {}).get('parameters', {})
            final_strategy_parameters = final_learning_config.get('strategy', {}).get('parameters', {})

            # merge statistics info
            for p, v in best_result.items():
                if type(v) in (str, int, float, bool):
                    final_learning_config[p] = v

            for pname, value in best_result_strategy_parameters.items():
                final_strategy_parameters[pname] = value

            # keep others best results for further analysis
            final_learning_config['results'] = self._trainer_commander.results

            # and finally update the learning file
            utils.write_learning(options, self._learning, final_learning_config)

        logger.debug("join commander")
        self._trainer_commander.join()
        self._trainer_commander = None

        return True

    def terminate(self, options):
        if self._watcher_service:
            self._watcher_service.terminate()

        Database.terminate()

        return True

    def forced_interrupt(self, options):
        logger.debug("kill commander")
        self._trainer_commander.kill()
        self._trainer_commander = None

        return True


tool = TrainerTool
