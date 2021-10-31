# @date 2019-06-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal commands

import json

from app.appexception import CommandHandlerException, CommandException, CommandAutocompleteException, \
    CommandParseException, CommandExecException
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.command')
error_logger = logging.getLogger('siis.error.command')


class Command(object):

    SUMMARY = ""
    HELP = tuple()

    def __init__(self, command_name, command_alias=None, accelerator=None, is_user=False):
        """
        @param command_name Advanced command identifier (must be unique)
        @param command_alias Short or alias for the command identifier (must be unique)
        @param accelerator Simple key for direct command (must be unique)
        @param is_user True mean its a user contextual command

        If a command_name start with _ it will be only accepted using its accelerator,
        and not display in the cli help.
        """
        self._name = command_name
        self._alias = command_alias
        self._accelerator = accelerator
        self._is_user = is_user

    @classmethod
    def summary(cls):
        return cls.SUMMARY

    @classmethod
    def help(cls):
        return cls.HELP

    @property
    def name(self):
        return self._name

    @property
    def alias(self):
        return self._alias

    @property
    def accelerator(self):
        return self._accelerator

    @property
    def is_user(self):
        return self._is_user

    def default_args(self):
        return []

    def execute(self, args):
        """
        Override this method to perform the command.

        @param args list without the first name of the command
        @return A tuple(boolean, None or str or list(str) or tuple(str)) Results status, list of message str to display.
        """
        return True, None

    def completion(self, args, tab_pos, direction):
        """
        Overrides this method to perform completion.

        @param args list without the first name of the command
        @param tab_pos integer next tab index
        @param direction integer 1 or -1
        """
        return args, tab_pos

    def iterate(self, index, values, args, tab_pos, direction):
        """
        Iterate the possibles values of a list for an argument index.
        """
        if not values:
            return args, 0

        if len(args) > index:
            filtered = []
            for v in values:
                if v.startswith(args[index]):
                    filtered.append(v)

            values = filtered

            if not values:
                return args, 0

        if tab_pos >= len(values):
            if direction < 0:
                tab_pos = len(values)-1
            elif direction > 0:
                tab_pos = 0
        elif tab_pos < 0:
            if direction < 0:
                tab_pos = len(values)-1
            elif direction > 0:
                tab_pos = 0

        if len(args) == index-1:
            args.append(values[0])
        else:
            args[index] = values[tab_pos]

        return args, tab_pos

    def manage_results(self, results, ok_message=None):
        if results is None:
            return False, "Invalid command results"

        if type(results) is dict:
            # single results
            if 'error' not in results:
                return False, "Invalid command results format"

            if results['error']:
                return False, results.get('messages', "")

            messages = results.get('messages')

            if ok_message:
                if messages:
                    if type(messages) in (list, tuple):
                        return True, messages + [ok_message]
                    elif type(messages) is str:
                        return True, [messages] + [ok_message]

                return True, ok_message

            return True, messages

        elif type(results) in (tuple, list):
            # multiples-results
            messages = []
            succeed = 0
            failed = 0

            for r in results:
                if r is None:
                    failed += 1
                    messages.append("Invalid command results")
                    continue

                if 'error' not in r:
                    failed += 1
                    messages.append("Invalid command results format")
                    continue

                if r['error']:
                    # partial error
                    failed += 1
                    msg = r.get('messages', [])
                    if type(msg) in (list, tuple):
                        messages += msg
                    elif type(msg) is str:
                        messages.append(msg)
                else:
                    # partial success
                    succeed += 1
                    msg = r.get('messages', [])
                    if type(msg) in (list, tuple):
                        messages += msg
                    elif type(msg) is str:
                        messages.append(msg)

            if succeed > 0 and failed > 0:
                messages.append("Partially succeed %i, failed %i" % (succeed, failed))
                messages.append(ok_message)
            elif succeed > 0 and failed == 0:
                messages.append("Fully succeed %i" % succeed)
                messages.append(ok_message)
            elif succeed == 0 and failed > 0:
                messages.append("Fully failed %i" % failed)

            return not failed, messages

        else:
            return False, "Invalid command results"


class CommandsHandler(object):
    """
    Process direct key and advanced command.
    Offers history, aliases with shortcut, and completion.

    F(X) keys are used for aliases.

    @todo For the command name (first arguments) if erase some characters,
        then it is not able to auto complete until ESC key is pressed.
        But have to move accelerator into command and move the complete code of 
        input to this object, then distinct more finely command or direct mode.
    """

    def __init__(self):
        self._commands = {}
        self._alias = {}
        self._accelerators = {}

        self._aliases = {}
        self._history = []
        self._history_pos = 0
        self._current = []
        self._tab_pos = -1
        self._word = ""

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
                "aliases": self._aliases,
            }, indent=4)
            
            f.write(dump.encode('utf-8'))

            f.close()
        except Exception as e:
            logger.error(repr(e))

    def register(self, command):
        """
        Register a new command with unique id, optional alias and optional accelerator.
        """
        if not command.name:
            raise CommandHandlerException("", "Missing command name")

        if command.name in self._commands:
            raise CommandException(command.name, "Already registered")

        if command.name in self._alias:
            raise CommandException(command.name, "Must not refers to a registered alias")

        if command.alias and command.alias in self._alias:
            raise CommandException(command.name, "Alias %s already registered" % (command.alias,))

        if command.accelerator and command.accelerator in self._accelerators:
            raise CommandException(command.name, "Accelerator %s already registered" % (command.accelerator,))

        if command.alias and command.alias in self._commands:
            raise CommandException(command.name, "Alias %s must not refers to another command" % (command.alias,))

        self._commands[command.name] = command
        if command.alias:
            self._alias[command.alias] = command.name

        if command.accelerator:
            self._accelerators[command.accelerator] = command.name

    def print_exec_msg(self, command_name, success, msgs):
        """
        Display to the terminal the results of a command execution.
        If the msgs is a single str or None it will be displayed as an error, else as an action.
        If the msgs list if None a default message is displayed as an error or an action.
        If the msgs is a str it is displayed as an error or an action.
        If the msgs is a list or a tuple the messages will be displayed in console.
        If the msgs is an empty list it will display nothing more than the command could have already
        displayed internally.
        """
        if msgs is None:
            if success:
                Terminal.inst().action("Command %s done" % command_name, view='status')
                Terminal.inst().action("Command %s done" % command_name, view='content')
            else:
                Terminal.inst().error("Command %s failed" % command_name, view='status')
                Terminal.inst().error("Command %s failed" % command_name, view='content')
        else:
            if success:
                if type(msgs) == str:
                    Terminal.inst().action(msgs, view='status')
                    Terminal.inst().action(msgs, view='content')
                elif type(msgs) == list or type(msgs) == tuple:
                    for msg in msgs:
                        Terminal.inst().action(msg, view='content')
            else:
                if type(msgs) == str:
                    Terminal.inst().error(msgs, view='status')
                    Terminal.inst().error(msgs, view='content')
                elif type(msgs) == list or type(msgs) == tuple:
                    for msg in msgs:
                        Terminal.inst().error(msg, view='content')

    def process_accelerator(self, key):
        """
        Process from accelerator (key shortcut).
        """
        command_name = self._accelerators.get(key)
        if command_name:
            command = self._commands.get(command_name)
            if command:
                try:
                    success, msgs = command.execute(command.default_args())
                    self.print_exec_msg(command_name, success, msgs)
                except Exception as e:
                    logger.error(str(e))
                    return False

                return True

        return False

    def process_cli(self, command_line):
        """
        Process from advanced command line.
        """
        if command_line.startswith(':'):
            args = [arg for arg in command_line[1:].split(' ') if arg]
            if command_line[-1] == ' ':
                args.append('')
        else:
            args = []

        if len(args):
            cmd = args[0]

            if cmd.startswith('_'):
                return False

            if not self._history or (self._history and ([cmd, *args[1:]] != self._history[-1])):
                self._history.append([cmd, *args[1:]])
    
            self._history_pos = 0
            self._current = []

            if cmd in self._commands:
                try:
                    success, msgs = self._commands[cmd].execute(args[1:])
                    self.print_exec_msg(cmd, success, msgs)
                except Exception as e:
                    logger.error(str(e))
                    return False

                return True

            elif cmd in self._alias:
                command_name = self._alias[cmd]
                if command_name in self._commands:
                    try:
                        success, msgs = self._commands[command_name].execute(args[1:])
                        self.print_exec_msg(command_name, success, msgs)
                    except Exception as e:
                        logger.error(str(e))
                        return False

                    return True

        return False

    def iterate_cmd(self, values, cmd, tab_pos, direction):
        """
        Iterate the possibles values of a list for the command.
        """
        if not values:
            return "", 0

        if cmd:
            filtered = []
            for v in values:
                if v.startswith(cmd):
                    filtered.append(v)

            values = filtered

            if not values:
                return cmd, 0

        if tab_pos >= len(values):
            if direction < 0:
                tab_pos = len(values)-1
            elif direction > 0:
                tab_pos = 0
        elif tab_pos < 0:
            if direction < 0:
                tab_pos = len(values)-1
            elif direction > 0:
                tab_pos = 0

        cmd = values[tab_pos]

        return cmd, tab_pos

    def process_cli_completion(self, args, tab_pos, direction):
        """
        Process work completion from advanced command line.
        """
        try:
            if len(args):
                cmd = args[0]

                if cmd.startswith('_'):
                    return args, tab_pos

                self._history_pos = 0

                if len(args) > 1:
                    if cmd in self._commands:
                        largs, tp = self._commands[cmd].completion(args[1:], tab_pos+direction, direction)
                        return [cmd, *largs], tp

                    elif cmd in self._alias:
                        command_name = self._alias[cmd]
                        if command_name in self._commands:
                            largs, tp = self._commands[command_name].completion(args[1:], tab_pos+direction, direction)
                            return [cmd, *largs], tp
                else:
                    cmds = list(self._commands.keys()) + list(self._alias.keys())
                    cmds.sort()

                    cmd, tp = self.iterate_cmd(cmds, cmd, self._tab_pos+direction, direction)

                    return [cmd], tp
            else:
                cmds = list(self._commands.keys()) + list(self._alias.keys())
                cmds.sort()

                cmd, tp = self.iterate_cmd(cmds, self._word, self._tab_pos+direction, direction)

                return [cmd], tp

        except Exception as e:
            error_logger.error(str(e))

        return args, tab_pos

    def get_command_help(self, command_name):
        """
        Return a list of triplets containing advanced command name, alias (can be None) and detailed help (can be empty).
        """
        command = self._commands.get(command_name)
        if command:
            return command.name, command.alias, command.help()

        return None, None, None

    def get_cli_summary(self):
        """
        Return a list of triplets containing advanced command identifier, alias (can be None) and summary help (can be empty).
        """
        result = []

        for k, command in self._commands.items():
            if not command.name.startswith('_'):
                result.append((command.name, command.alias, command.summary()))

        return result

    def get_summary(self):
        """
        Return a list of couples containing simple command with accelerator and summary help (can be empty).
        """
        result = []

        for k, command_name in self._accelerators.items():
            command = self._commands.get(command_name)
            if command and not command.is_user:
                result.append((command.accelerator, command.summary()))

        return result

    def get_user_summary(self):
        """
        For user context only, return a list of couples containing simple command with accelerator and summary help (can be empty).
        """
        result = []

        for k, command_name in self._accelerators.items():
            command = self._commands.get(command_name)
            if command and command.is_user:
                result.append((command.accelerator, command.summary()))

        return result

    def set_alias(self, key_code, args):
        if key_code and args:
            self._aliases[key_code] = args

    def reset_alias(self, key_code):
        if key_code in self._aliases:
            del self._aliases[key_code]

    def process_char(self, char, args):
        """
        Process a character on the command handler.
        """
        if not char:
            return

        if char == ' ':
            # next word
            self._word = ""
        elif char == '\b':
            self._word = args[-1][:-1] if args else ""
        elif char == '\n':
            self._word = ""
        else:
            # same word
            self._word += char

        if len(args) <= 1 and self._word and self._word[0] != ':':
            # command starts with a semicolumn
            self._word = ""

        # each time a char is typed current completion is reset
        self._tab_pos = -1

    def process_key(self, key_code, args, command_mode):
        """
        Process a key on the command handler.
        """
        if key_code in self._aliases:
            self._current = []
            self._history_pos = 0
            self._word = ""
            self._tab_pos = -1

            return self._aliases[key_code]

        elif key_code == 'KEY_ESCAPE' and command_mode:
            self._current = []
            self._history_pos = 0
            self._word = ""
            self._tab_pos = -1

            return []

        elif key_code == 'KEY_STAB' and command_mode:
            args, self._tab_pos = self.process_cli_completion([*args[:-1], self._word.lstrip(':')], self._tab_pos, 1)
            return args

        elif key_code == 'KEY_BTAB' and command_mode:
            args, self._tab_pos = self.process_cli_completion([*args[:-1], self._word.lstrip(':')], self._tab_pos, -1)
            return args

        elif key_code == 'KEY_UP' and command_mode:
            if self._history:
                if (len(self._history) + self._history_pos > 0):
                    if self._history_pos == 0:
                        self._current = args

                    self._history_pos -= 1
                    return self._history[self._history_pos]

        elif key_code == 'KEY_DOWN' and command_mode:
            if self._history:
                if self._history_pos < 0:
                    self._history_pos += 1
                    return self._history[self._history_pos]
                else:
                    self._word = self._current[-1] if self._current else ""
                    return self._current

        return args
