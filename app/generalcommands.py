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


def register_general_commands(commands_handler):
    cmd = HelpCommand(commands_handler)
    commands_handler.register(cmd)

    cmd = UserHelpCommand(commands_handler)
    commands_handler.register(cmd)
