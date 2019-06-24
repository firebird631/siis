# @date 2019-06-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# terminal commands

import json

import logging
logger = logging.getLogger('siis.command')


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

    def completion(self, args, tab_pos):
        return args, tab_pos


class CommandsHandler(object):
    """
    Process direct key and advanced command.
    Offers history, aliases with shortcut, and completion.

    F(X) keys are used for aliases.
    """

    def __init__(self):
        self._commands = {}
        self._alias = {}
        self._accelerators = {}

        self._aliases = {}
        self._history = []
        self._history_pos = 0
        self._current = []
        self._tab_pos = 0

    def init(self, config):
        filename = config.get('config-path', '.') + '/' + "history.json"

        try:
            f = open(filename, "rb")
            data = json.loads(f.read())
            f.close()

            self._history = data.get('commands', [])
            self._aliases = data.get('aliases', {})

        except FileNotFoundError as e:
            pass
        except json.JSONDecodeError as e:
            pass
        except Exception as e:
            logger.error(repr(e))

    def terminate(self, config):
        filename = config.get('config-path', '.') + '/' + "history.json"

        try:
            f = open(filename, "wb")
            
            dump = json.dumps({
                "commands": self._history,
                "aliases": self._aliases
            })
            
            f.write(dump.encode('utf-8'))

            f.close()
        except Exception as e:
            logger.error(repr(e))

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
        if command_line.startswith(':'):
            args = command_line[1:].split(' ')
        else:
            args = []

        if len(args):
            cmd = args[0]

            if not self._history or (self._history and ([cmd, *args[1:]] != self._history[-1])):
                self._history.append([cmd, *args[1:]])
    
            self._history_pos = 0
            self._current = []

            if cmd in self._commands:
                return self._commands[cmd].execute(args[1:])

            elif cmd in self._alias:
                command_id = self._alias[cmd]
                if command_id in self._commands:
                    return self._commands[command_id].execute(args[1:])

        return False

    def process_cli_completion(self, args, tab_pos):
        """
        Process work completion from advanced command line.
        """
        if len(args):
            cmd = args[0]

            self._history_pos = 0

            if cmd in self._commands:
                largs, tp = self._commands[cmd].completion(args[1:], tab_pos)
                return [cmd, *largs], tp

            elif cmd in self._alias:
                command_id = self._alias[cmd]
                if command_id in self._commands:
                    largs, tp = self._commands[command_id].completion(args[1:], tab_pos)
                    return [cmd, *largs], tp

        return args, tab_pos

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
        """
        if key_code in self._aliases:
            self._current = []
            self._history_pos = 0

            return self._aliases[key_code]

        elif key_code == 'KEY_ESCAPE':
            self._current = []
            self._history_pos = 0

        elif key_code == 'KEY_STAB':
            self._tab_pos += 1
            args, self._tab_pos = self.process_cli_completion(args, self._tab_pos)

            return args

        elif key_code == 'KEY_BTAB':
            self._tab_pos = max(0, self._tab_pos-1)
            args, self._tab_pos = self.process_cli_completion(args, self._tab_pos-1)

            return args

        elif key_code == 'KEY_UP':
            if self._history:
                if (len(self._history) + self._history_pos > 0):
                    if self._history_pos == 0:
                        self._current = args

                    self._history_pos -= 1
                    return self._history[self._history_pos]

        elif key_code == 'KEY_DOWN':
            if self._history:
                if self._history_pos < 0:
                    self._history_pos += 1
                    return self._history[self._history_pos]
                else:
                    return self._current

        # @todo manage tab-key for completion
        # @todo manage left/right key for cursor
        # @todo manage ctrl-backspace for word cut

        return args
