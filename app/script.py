# @date 2021-10-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# General script handler.

import sys

from importlib import import_module, reload

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

    if action == "exec":
        # an exec first reload the module in case its content has changed
        try:
            module_name = "userscripts.%s" % module

            if module_name in sys.modules.keys():
                # next imports
                results['messages'].append("User script %s previously loaded, reload it..." % module)
                script_module = reload(sys.modules[module_name])
            else:
                # initial import
                results['messages'].append("User script %s initial load..." % module)
                script_module = import_module(module_name, package='')

        except ModuleNotFoundError as e:
            results['messages'].append("Module %s not found" % module)
            results['error'] = True
            return results

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
            results['messages'].append("The script %s does not have a run_once method" % module)
            results['error'] = True
            return results

    elif action == "remove":
        # a remove use the current loaded module, not the new version
        module_name = "userscripts.%s" % module

        # reuse last import
        if module_name in sys.modules.keys():
            script_module = sys.modules[module_name]
        else:
            results['messages'].append("Module %s not found, it cannot be removed" % module)
            results['error'] = True
            return results

        if hasattr(script_module, 'remove'):
            # remove script
            remove = getattr(script_module, 'remove')

            try:
                results = remove(watcher_service, trader_service, strategy_service, monitor_service, notifier_service)
            except Exception as e:
                results['messages'].append(repr(e))
                results['error'] = True
                return results
        else:
            results['messages'].append("The script %s does not have a remove method" % module)
            results['error'] = True

            return results

    elif action == "unload":
        # unload current loaded module
        module_name = "userscripts.%s" % module

        # reuse last import
        if module_name in sys.modules.keys():
            script_module = sys.modules[module_name]
        else:
            results['messages'].append("Module %s not found, it cannot be unloaded" % module)
            results['error'] = True
            return results

        results['messages'].append("Unload module %s" % module)

        script_module = None  # unref
        del sys.modules[module_name]

        return results

    return results
