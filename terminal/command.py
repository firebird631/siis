# @date 2019-06-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal commands

class Command(object):

    def __init__(self, command_id, command_alias=None, accelerator=None, is_user=False):
        """
        @param command_id Advanced command identifier (must be unique)
        @param command_alias Short or alias for the command identifier (must be unique)
        @param accelerator Simple key for direct command (must be unique)
        @param is_user True mean its a user contextual command
        """
        self._id = command_id
        self._alias = command_alias
        self._accelerator = accelerator
        self._help = ""
        self._is_user = is_user

    @property
    def id(self):
        return self._id

    @property
    def alias(self):
        return self._alias

    @property
    def accelerator(self):
        return self._accelerator

    @property
    def is_user(self):
        return self._is_user

    @property
    def help(self):
        return self._help

    def default_args(self):
        return []

    def execute(self, args):
        return True


class CommandsHandler(object):

    def __init__(self):
        self._commands = {}
        self._alias = {}
        self._accelerators = {}

        self._aliases = {}

    def register(self, command):
        """
        Register a new command with unique id, optionnal alias and optionnal accelerator.
        """
        if not command.id:
            raise InvalidValue("Missing command identifier")

        if command.id in self._commands:
            raise InvalidValue("Command %s already registred" % (command.id,))

        if command.alias and command.alias in self._alias:
            raise InvalidValue("Command alias %s for %s already registred" % (command.alias, command.id))

        if command.accelerator and command.accelerator in self._accelerators:
            raise InvalidValue("Command accelerator %s for %s already registred" % (command.accelerator, command.id))

        if command.id in self._alias:
            raise InvalidValue("Command %s must not refers to a registred alias" % (command.id,))

        if command.alias and command.alias in self._commands:
            raise InvalidValue("Command alias %s for %s must not refers to another command" % (command.alias, command.id))

        self._commands[command.id] = command

        if command.alias:
            self._alias[command.alias] = command.id

        if command.accelerator:
            self._accelerators[command.accelerator] = command.id

    def unregister(self, command_id):
        command = self._commands.get(command_id)
        if command:
            if command.alias in self._alias:
                del self._alias[command_id]

            if command.accelerator in self._accelerators:
                del self._accelerators[command_id]

            del self._commands[command_id]

    def process_accelerator(self, key):
        """
        Process from accelerator (key shortcut).
        """
        command_id = self._accelerators.get(key)
        if command_id:
            command = self._commands.get(command_id)
            if command:
                command.execute(command.default_args())

    def process_cli(self, command_line):
        """
        Process from advanced command line.
        """
        args = command_line.split(' ')

        if len(args):
            cmd = args[0].lstrip(':')  # remove the trailing ':' if necessary

            if cmd in self._commands:
                return self._commands[cmd].execute(args[1:])

            elif cmd in self._alias:
                command_id = self._alias[cmd]
                if command_id in self._commands:
                    return self._commands[command_id].execute(args[1:])

        return False

    def get_cli_help(self):
        """
        Return a list of triplets containing advanced command identifier, alias (can be None) and detailed command help (can be empty).
        """
        result = []

        for k, command in self._commands.items():
            result.append((command.id, command.alias, command.help))
        
        return result

    def get_help(self):
        """
        Return a list of couples containing simple command with accelerator and detailed command help (can be empty).
        """
        result = []

        for k, command in self._accelerators.items():
            if not command.is_user:
                result.append((command.accelerator, command.help))
        
        return result

    def get_user_help(self):
        """
        For user context only, return a list of couples containing simple command with accelerator and detailed command help (can be empty).
        """
        result = []

        for k, command in self._accelerators.items():
            if command.is_user:
                result.append((command.accelerator, command.help))

        return result

    def set_alias(self, key_code, args):
        if key_code and args:
            self._aliases[key_code] = args

    def reset_alias(self, key_code):
        if key_code in self._aliases:
            del self._aliases[key_code]

    def process_key(self, key_code, args):
        """
        Process a key on the command handler.
        F(X) keys are used for aliases.
        """
        if key_code in self._aliases:
            return self._aliases[key_code]

        # @todo manage tab-key for completation
        # @todo manage left/right key for cursor
        # @todo manage ctrl-backspace for word cut

        return args
