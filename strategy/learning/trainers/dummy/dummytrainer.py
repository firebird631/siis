# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer base class

import copy
import math
import random

from datetime import datetime

from common.utils import truncate
from strategy.learning.trainer import Trainer, TrainerCommander, TrainerCaller


class DummyTrainerCaller(TrainerCaller):

    def __init__(self):
        self.fitness = 0.0
        self.training_result = None

    def set_result(self, results):
        if results is not None:
            # unpack results
            self.fitness = results[0]
            self.training_result = results[1]


class DummyTrainerCommander(TrainerCommander):
    """
    Simple random draw as example purpose but could give sometime good results.
    """

    def __init__(self, profile_name: str, profile_parameters: dict, learning_parameters: dict):
        super().__init__(profile_name, profile_parameters, learning_parameters)

        trainer_params = learning_parameters.get('trainer', {})

        self._num_gen = trainer_params.get('num-gen', 5)

        try:
            self._min_perf = float(learning_parameters.get('trainer', {}).get('min-performance', "0.00%").rstrip('%'))
        except ValueError:
            self._min_perf = 0.0

        self._results = []
        self._finals = []

    def start(self, callback: callable):
        random.seed()

        n = 0
        while 1:
            # generate rand parameters
            trainer_params = copy.deepcopy(self._learning_parameters.get('trainer', {}))
            trader_params = copy.deepcopy(self._learning_parameters.get('trader', {}))
            watchers_params = copy.deepcopy(self._learning_parameters.get('watchers', {}))
            strategy_params = {}

            for param_info in self._params_info:
                strategy_params[param_info['name']] = DummyTrainerCommander.set_rand_value(param_info)

            learning_parameters = {
                'created': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                'trader': trader_params,
                'watchers': watchers_params,
                'trainer': trainer_params,
                'strategy': {'parameters': strategy_params}
            }

            # start training
            if self._parallel > 1:
                # async parallels
                caller = DummyTrainerCaller()
                self._results.append(caller)

                self.start_job(caller, callback, learning_parameters, self._profile_name)
            else:
                # synchronous 1 by 1
                fitness, trainer_result = callback(learning_parameters, self._profile_name, None)
                # print(fitness)
                # print(training_result)

                try:
                    performance = float(trainer_result.get('performance', "0.00%").rstrip('%'))
                except ValueError:
                    continue

                if performance >= self._min_perf:
                    # keep only if min perf is reached
                    self._finals.append(trainer_result)

            n += 1

            if n >= self._num_gen:
                break

        if self._parallel > 1:
            self.join()

            for result in self._results:
                # synchronous 1 by 1
                fitness = result.fitness
                trainer_result = result.training_result
                # print(fitness)
                # print(training_result)

                if not trainer_result:
                    continue

                try:
                    performance = float(trainer_result.get('performance', "0.00%").rstrip('%'))
                except ValueError:
                    continue

                if performance >= self._min_perf:
                    # keep only if min perf is reached
                    self._finals.append(trainer_result)

    @property
    def results(self) -> list:
        return self._finals

    @staticmethod
    def set_rand_value(param: dict):
        if param.get('type') == "int":
            return random.randrange(param.get('min', 0), param.get('max', 0) + 1, param.get('step', 1))

        elif param.get('type') == "float":
            precision = param.get('precision', 1) or 1
            step = param.get('step', 0.01) or 0.01

            number = random.randrange(
                param.get('min', 0) * math.pow(10, precision),
                param.get('max', 0) * math.pow(10, precision) + 1, 1) * math.pow(10, -precision)

            return truncate(round(number / step) * step, precision)

        else:
            return 0

    def estimate_duration(self, avg_job_time: float) -> float:
        return (self._num_gen - self._executed_jobs) / self._parallel * avg_job_time

    def progress(self) -> float:
        return self._executed_jobs / self._num_gen * 100.0


class DummyTrainer(Trainer):
    """
    Random based parameters generator method.
    """

    NAME = "dummy"
    COMMANDER = DummyTrainerCommander
