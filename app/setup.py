# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Application setup

import sys
import os
import pathlib


def install(options):
    config_path = "./"
    data_path = "./"

    home = pathlib.Path.home()
    if home.exists():
        if sys.platform == "linux":
            user_path = pathlib.Path(home, '.siis')

            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
            reports_path = pathlib.Path(home, '.siis', 'reports')
            markets_path = pathlib.Path(home, '.siis', 'markets')
            learning_path = pathlib.Path(home, '.siis', 'learning')
        elif sys.platform == "windows":
            app_data = os.getenv('APPDATA')

            user_path = pathlib.Path(home, app_data, '.siis')

            config_path = pathlib.Path(home, app_data, 'siis', 'config')
            log_path = pathlib.Path(home, app_data, 'siis', 'log')
            reports_path = pathlib.Path(home, app_data, 'siis', 'reports')
            markets_path = pathlib.Path(home, app_data, 'siis', 'markets')
            learning_path = pathlib.Path(home, app_data, 'siis', 'learning')
        else:
            user_path = pathlib.Path(home, '.siis')

            config_path = pathlib.Path(home, '.siis', 'config')
            log_path = pathlib.Path(home, '.siis', 'log')
            reports_path = pathlib.Path(home, '.siis', 'reports')
            markets_path = pathlib.Path(home, '.siis', 'markets')
            learning_path = pathlib.Path(home, '.siis', 'learning')
    else:
        # uses cwd
        home = pathlib.Path(os.getcwd())

        user_path = pathlib.Path(home, 'user')

        config_path = pathlib.Path(home, 'user', 'config')
        log_path = pathlib.Path(home, 'user', 'log')
        reports_path = pathlib.Path(home, 'user', 'reports')
        markets_path = pathlib.Path(home, 'user', 'markets')
        learning_path = pathlib.Path(home, 'user', 'learning')

    # .siis/
    if not user_path.exists():
        user_path.mkdir(parents=True)

    options['user-path'] = str(user_path)

    # config/
    if not config_path.exists():
        config_path.mkdir(parents=True)

    if not config_path.joinpath("profiles").exists():
        config_path.joinpath("profiles").mkdir(parents=True)

    if not config_path.joinpath("watchers").exists():
        config_path.joinpath("watchers").mkdir(parents=True)

    if not config_path.joinpath("traders").exists():
        config_path.joinpath("traders").mkdir(parents=True)

    options['config-path'] = str(config_path)

    # markets/
    if not markets_path.exists():
        markets_path.mkdir(parents=True)

    options['markets-path'] = str(markets_path)

    # reports/
    if not reports_path.exists():
        reports_path.mkdir(parents=True)

    options['reports-path'] = str(reports_path)

    # learning/
    if not learning_path.exists():
        learning_path.mkdir(parents=True)

    options['learning-path'] = str(learning_path)

    # log/
    if not log_path.exists():
        log_path.mkdir(parents=True)

    options['log-path'] = str(log_path)
