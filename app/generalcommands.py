# @date 2019-06-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal general commands and registration

from terminal.command import Command

from app.help import display_help, display_cli_help


class HelpCommand(Command):

    def __init__(self, commands_handler):
        super().__init__('help', 'h')

        self._commands_handler = commands_handler
        self._help = "for this help"

    def execute(self, args):
        display_help(self._commands_handler)
        return True


class UserHelpCommand(Command):

    def __init__(self, commands_handler):
        super().__init__('user', 'u')

        self._commands_handler = commands_handler
        self._help = "to display contextual user help"

    def execute(self, args):
        display_help(self._commands_handler, True)
        return True


class AliasCommand(Command):

    def __init__(self, commands_handler):
        super().__init__('alias', '@')

        self._commands_handler = commands_handler
        self._help = "to set an alias for a command"

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

        commands_handler.set_alias(key_code, args[1:])
        return True


class UnaliasCommand(Command):

    def __init__(self, commands_handler):
        super().__init__('unalias', '^')

        self._commands_handler = commands_handler
        self._help = "to unset an alias of command"

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

        commands_handler.reset_alias(key_code)
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
