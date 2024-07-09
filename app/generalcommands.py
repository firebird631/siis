# @date 2019-06-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal general commands and registration

import sys

from terminal.command import Command

from app.help import display_help, display_command_help, display_version
from terminal.terminal import Terminal


class QuitCommand(Command):

    SUMMARY = "<save> <term> exit application"

    HELP = (
        "optional parameters only for live mode:",
        "<save> write current states into the database before exit",
        "<term> delete any non realized trades before exit.")

    CHOICES = ("save", "term")

    def __init__(self, strategy_service):
        super().__init__('quit', None)

        self._strategy_service = strategy_service

    def execute(self, args):
        if self._strategy_service:
            self._strategy_service.set_save_on_exit('save' in args)
            self._strategy_service.set_terminate_on_exit('term' in args)

        if hasattr(sys.modules['__main__'], "running"):
            setattr(sys.modules['__main__'], "running", False)

        return True, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 2:
            return self.iterate(len(args)-1, list(QuitCommand.CHOICES), args, tab_pos, direction)

        return args, 0


class HelpCommand(Command):

    SUMMARY = "for this help or help with a specific command name"

    def __init__(self, commands_handler):
        super().__init__('help', 'h')

        self._commands_handler = commands_handler

    def execute(self, args):
        if not args:
            display_help(self._commands_handler)
            return True, []
        elif len(args) == 1:
            display_command_help(self._commands_handler, args[0])
            return True, []

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._commands_handler.get_command_list(), args, tab_pos, direction)

        return args, 0


class UserHelpCommand(Command):

    SUMMARY = "to display contextual user help"
    
    def __init__(self, commands_handler):
        super().__init__('user', 'u')

        self._commands_handler = commands_handler

    def execute(self, args):
        if not args:
            display_help(self._commands_handler, True)
            return True, []
        elif len(args) == 1:
            display_command_help(self._commands_handler, args[0])
            return True, []

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, self._commands_handler.get_command_list(), args, tab_pos, direction)

        return args, 0


class VersionCommand(Command):

    SUMMARY = "display version"

    def __init__(self):
        super().__init__('version', 'v')

    def execute(self, args):
        if not args:
            display_version()
            return True, []

        return False, None


class AliasCommand(Command):

    SUMMARY = "to set an alias for a command"
    
    def __init__(self, commands_handler):
        super().__init__('alias', '@')

        self._commands_handler = commands_handler

    def execute(self, args):
        if len(args) < 2:
            return False, "Missing parameters"

        key = args[0]
        key_code = ""

        if key.startswith("F") and 2 <= len(key) <= 3:
            try:
                num = int(key[1:])
            except ValueError:
                return False, "Invalid key-code"

            key_code = "KEY_F(%i)" % num

        if not key_code:
            return False, "Invalid key-code"

        self._commands_handler.set_alias(key_code, args[1:])
        return True, None


class UnaliasCommand(Command):

    SUMMARY = "to unset an alias of command"
    
    def __init__(self, commands_handler):
        super().__init__('unalias', '^')

        self._commands_handler = commands_handler

    def execute(self, args):
        if len(args) != 1:
            return False, "Missing parameters"

        key = args[0]
        key_code = ""

        if key.startswith("F") and 2 <= len(key) <= 3:
            try:
                num = int(key[1:])
            except ValueError:
                return False, "Invalid key-code"

            key_code = "KEY_F(%i)" % num

        if not key_code:
            return False, "Invalid key-code"

        self._commands_handler.reset_alias(key_code)
        return True, None


class MemoCommand(Command):

    SUMMARY = "simply memo few messages and retrieve them later"

    def __init__(self, commands_handler):
        super().__init__('memo', None)

        self._commands_handler = commands_handler
        self._memos = []

    def execute(self, args):
        if len(args) == 0:
            Terminal.inst().message("Memo contains %i messages :" % len(self._memos), view="content")

            for i, msg in enumerate(self._memos):
                Terminal.inst().message("  - #%i: %s" % (i+1, msg), view="content")

            return True, None
        else:
            msg = " ".join(args)
            if msg:
                self._memos.append(msg)

                return True, "Memo recorded. Type memo without parameters to retrieve them all"
            else:
                return True, "No message to record"


def register_general_commands(commands_handler, strategy_service):
    commands_handler.register(QuitCommand(strategy_service))
    commands_handler.register(HelpCommand(commands_handler))
    commands_handler.register(UserHelpCommand(commands_handler))
    commands_handler.register(VersionCommand())
    commands_handler.register(AliasCommand(commands_handler))
    commands_handler.register(UnaliasCommand(commands_handler))
    commands_handler.register(MemoCommand(commands_handler))
