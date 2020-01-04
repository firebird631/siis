# @date 2020-01-03
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Base tools model

import sys
import logging
import traceback
import glob

from os.path import dirname, basename, isfile, join
from importlib import import_module

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.tools')
error_logger = logging.getLogger('siis.error.tools')


class Tool(object):
    """
    Base tools model.
    """

    def __init__(self, name, options):
        self._name = name
        self._state = 0

    @classmethod
    def alias(cls):
        """Return an alias name for the tool or None."""
        return None

    @classmethod
    def help(cls):
        """Return the CLI help message."""
        return tuple()

    @classmethod
    def detailed_help(cls):
        """Return the CLI detailed help message."""
        return tuple()

    @classmethod
    def need_identity(cls):
        """Return True if the tools need the identity specified."""
        return False

    def check_options(self, options):
        """Checks arguments for options from command line and return True if pass."""
        return True

    def init(self, options):
        """Initialization step, before run."""
        return True

    def run(self, options):
        """Main entry of the tool"""
        return True

    def forced_interrupt(self, options):
        """Interruption forced during processing."""
        return True

    def terminate(self, options):
        """Termination step, before run."""
        return True

    def execute(self, options):
        try:
            self._state = 0

            if not self.check_options(options):
                error_logger.error("Invalid arguments")

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            self._state = 1

            if not self.init(options):
                error_logger.error("Unable to initiate tool %s" % self._name)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            self._state = 2

            if not self.run(options):
                error_logger.error("Error during execution of tool %s" % self._name)

                # cleanup before exit
                self.terminate(options)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            self._state = 3

            if not self.terminate(options):
                error_logger.error("Error during termination of tool %s" % self._name)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            self._state = 4

        except KeyboardInterrupt:
            if self._state in (0, 1, 4):
                error_logger.error("User forced termination of tool %s before it process" % self._name)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            elif self._state == 2:
                error_logger.error("User forced termination of tool %s during process" % self._name)

                # cleanup before exit
                self.forced_interrupt(options)
                self.terminate(options)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

            elif self._state == 3:
                error_logger.error("User forced termination of tool %s after it process" % self._name)

                # cleanup before exit
                self.terminate(options)

                Terminal.inst().flush()
                Terminal.terminate()

                sys.exit(-1)

        except Exception as e:
            error_logger.error(str(e))
            sys.exit(-1)

    @staticmethod
    def find_tools():
        """Return the list of tools found into the tools module."""
        modules = glob.glob(join(dirname(__file__), "*.py"))
        __all__ = [basename(f)[:-3] for f in modules if isfile(f)]

        __all__.remove("__init__")
        __all__.remove("tool")

        return __all__

    @staticmethod
    def load_tool(name):
        """Load the module for the tool specified by name and return its class model (not an instance)"""
        tools = Tool.find_tools()
        if name in tools:
            try:
                module = import_module("tools.%s" % name, package='')
                ToolClazz = getattr(module, "tool", None)

                if not ToolClazz:
                    error_logger.error("Tool %s not found in its module" % name)

                return ToolClazz

            except ModuleNotFoundError as e:
                error_logger.error("Tool %s module not found" % name)
            except Exception as e:
                error_logger.error("Error during loading of the tool %s" % name)
        else:
            error_logger.error("Tool %s not found" % name)

        return None

    @staticmethod
    def tool_help(name):
        """Try to load the module for the tool specified by name and return its alias and help messages"""
        try:
            module = import_module("tools.%s" % name, package='')
            ToolClazz = getattr(module, "tool", None)

            if ToolClazz:
                return ToolClazz.alias(), ToolClazz.help()

        except ModuleNotFoundError as e:
            pass
        except Exception as e:
            pass

        return []

    @staticmethod
    def detailed_tool_help(name):
        """Try to load the module for the tool specified by name and return its alias and help detailed messages"""
        try:
            module = import_module("tools.%s" % name, package='')
            ToolClazz = getattr(module, "tool", None)

            if ToolClazz:
                return ToolClazz.alias(), ToolClazz.detailed_help()

        except ModuleNotFoundError as e:
            pass
        except Exception as e:
            pass

        return []
