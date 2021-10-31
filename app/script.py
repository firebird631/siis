# @date 2021-10-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# General script handler.

from importlib import import_module

import logging
logger = logging.getLogger('siis.app.script')
error_logger = logging.getLogger('siis.error.app.script')


def setup_script(action, module, watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    """
    Setup, load a module and run the script or remove an installed script.

    A script must be either have a run_once method with the following signature :
        def run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    and must at least return a command results dict with 'messages' and 'error' field or a list of a such dict.

    @todo cron script (need a registry)
    @todo run by a service script
    @todo remove a cron or a run by service script
    """
    results = {
        'messages': [],
        'error': False
    }

    if not action:
        results['messages'].append("Action must be exec or remove")
        results['error'] = True
        return results

    if not module:
        results['messages'].append("Module must be specified")
        results['error'] = True
        return results

    try:
        script_module = import_module("userscripts.%s" % module, package='')
    except ModuleNotFoundError as e:
        results['messages'].append("Module %s not found" % module)
        results['error'] = True
        return results

    if action == "exec":
        if hasattr(script_module, 'run_once'):
            # run once script
            run_once = getattr(script_module, 'run_once')

            try:
                results = run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service)
            except Exception as e:
                results['messages'].append(repr(e))
                results['error'] = True
                return results
        else:
            results['messages'].append("Unsupported script module %s format" % module)
            results['error'] = True
            return results

    elif action == "remove":
        pass  # @todo

    return results
