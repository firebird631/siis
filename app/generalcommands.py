# @date 2019-06-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal general commands and registration

from terminal.command import Command

from app.help import display_help, display_cli_help, display_command_help


class HelpCommand(Command):

    SUMMARY = "for this help"

    def __init__(self, commands_handler):
        super().__init__('help', 'h')

        self._commands_handler = commands_handler

    def execute(self, args):
        if not args:
            display_help(self._commands_handler)
            return True
        elif len(args) == 1:
            display_command_help(self._commands_handler, args[0])
            return True

        return False


class UserHelpCommand(Command):

    SUMMARY = "to display contextual user help"
    
    def __init__(self, commands_handler):
        super().__init__('user', 'u')

        self._commands_handler = commands_handler

    def execute(self, args):
        if not args:
            display_help(self._commands_handler, True)
            return True
        elif len(args) == 1:
            display_command_help(self._commands_handler, args[0])
            return True

        return False


class AliasCommand(Command):

    SUMMARY = "to set an alias for a command"
    
    def __init__(self, commands_handler):
        super().__init__('alias', '@')

        self._commands_handler = commands_handler

    def execute(self, args):
        if len(args) < 2:
            return False

        key = args[0]
        key_code = ""

        if key.startswith("F") and 2 <= len(key) <= 3:
            try:
                num = int(key[1:])
            except ValueError:
                return False

            key_code = "KEY_F(%i)" % num

        if not key_code:
            return False

        self._commands_handler.set_alias(key_code, args[1:])
        return True


class UnaliasCommand(Command):

    SUMMARY = "to unset an alias of command"
    
    def __init__(self, commands_handler):
        super().__init__('unalias', '^')

        self._commands_handler = commands_handler

    def execute(self, args):
        if len(args) != 1:
            return False

        key = args[0]
        key_code = ""

        if key.startswith("F") and 2 <= len(key) <= 3:
            try:
                num = int(key[1:])
            except ValueError:
                return False

            key_code = "KEY_F(%i)" % num

        if not key_code:
            return False

        self._commands_handler.reset_alias(key_code)
        return True


def register_general_commands(commands_handler):
    cmd = HelpCommand(commands_handler)
    commands_handler.register(cmd)

    cmd = UserHelpCommand(commands_handler)
    commands_handler.register(cmd)

    cmd = AliasCommand(commands_handler)
    commands_handler.register(cmd)

    cmd = UnaliasCommand(commands_handler)
    commands_handler.register(cmd)
