# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Application help

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_LONG_NAME

from terminal.terminal import Terminal


def display_help(commands_handler, user_context=False):
    if user_context:
        # user context help
        Terminal.inst().message("User contextuel commands:", view='content')
        for entry in commands_handler.get_user_summary():
            if entry[1]:
                Terminal.inst().message(" - '%s' %s " % (entry[0], entry[1]) , view='content')
    else:
        # general help
        Terminal.inst().message("General commands. Direct key actions (single key press), view key are in uppercase:", view='content')
        # @todo accelerator with Command
        Terminal.inst().message(" - '?' ping all services", view='content')
        Terminal.inst().message(" - <space> print a time mark in status bar", view='content')
        Terminal.inst().message(" - 'n' toggle desktop notifications", view='content')
        Terminal.inst().message(" - 'a' toggle audible notifications", view='content')
        Terminal.inst().message(" - 'e' toggle discord notifications", view='content')

        Terminal.inst().message(" - 'p' list positions (will be replaced by a dedicated view)", view='content')
        Terminal.inst().message(" - 'o' list orders (will be replaced by a dedicated view)", view='content')
        Terminal.inst().message(" - 'g' print trader performance (will be replaced by a dedicated view or removed)", view='content')

        Terminal.inst().message(" - 'A' show account view", view='content')
        Terminal.inst().message(" - 'Q' show assets view", view='content')        
        Terminal.inst().message(" - 'M' show markets view", view='content')
        Terminal.inst().message(" - 'T' show tickers view", view='content')
        Terminal.inst().message(" - 'F' show strategy view", view='content')
        Terminal.inst().message(" - 'S' show statistic view", view='content')
        Terminal.inst().message(" - 'P' show performance view", view='content')
        Terminal.inst().message(" - 'I' show console view", view='content')
        Terminal.inst().message(" - 'N' show notification/signal view", view='content')
        # Terminal.inst().message(" - 'U' list positions", view='content')
        # Terminal.inst().message(" - 'O' list orders", view='content')
        Terminal.inst().message(" - 'D' show debug view", view='content')
        Terminal.inst().message(" - 'C' clear current view", view='content')

        for entry in commands_handler.get_summary():
            if entry[1]:
                Terminal.inst().message(" - %s %s " % (entry[0], entry[1]) , view='content')

        Terminal.inst().message("", view='content')
        Terminal.inst().message("Advanced commands have to be completed by <ENTER> key else <ESC> to cancel. Command typing are avoided after fews seconds.", view='content')
        Terminal.inst().message(" - ':quit' or ':q' exit", view='content')

        for entry in commands_handler.get_cli_summary():
            if entry[2]:
                if entry[1]:
                    Terminal.inst().message(" - ':%s' or ':%s' %s " % (entry[0], entry[1], entry[2]) , view='content')
                else:
                    Terminal.inst().message(" - ':%s' %s " % (entry[0], entry[2]) , view='content')


def display_command_help(commands_handler, command_name):
    name, alias, details = commands_handler.get_command_help(command_name)

    if not name:
        Terminal.inst().message("Command %s not found" % command_name, view='content')
        return

    Terminal.inst().message("Details of the command %s" % name, view='content')
    if alias:
        Terminal.inst().message(" - Alias %s" % alias, view='content')

    if details:
        for entry in details:
            Terminal.inst().message(entry, view='content')


def display_cli_help():
    Terminal.inst().message("")
    Terminal.inst().message('%s command line usage:' % APP_LONG_NAME)
    Terminal.inst().message("")
    Terminal.inst().message("\tcmd <identity> <--options>")
    Terminal.inst().message("")
    Terminal.inst().message("\tProfile name must be defined in the identy.py file from .siis local data. With that way you can manage multiple account, having identity for demo.")
    Terminal.inst().message("\t --help display command line help.")
    Terminal.inst().message("\t --version display the version number.")
    Terminal.inst().message("\t --profile=<profile> Use a specific profile of appliance else default loads any.")
    Terminal.inst().message("\t --paper-mode instanciate paper mode trader and simulate as best as possible.")
    Terminal.inst().message("\t --backtest process a backtesting, uses paper mode traders and data history avalaible in the database.")
    Terminal.inst().message("\t --timestep=<seconds> Timestep in seconds to increment the backesting. More precise is more accurate but need more computing simulation. Adjust to at least fits to the minimal candles size uses in the backtested strategies. Default is 60 seconds.")
    Terminal.inst().message("\t --time-factor=<factor> in backtesting mode only allow the user to change the time factor and permit to interact during the backtesting. Default speed factor is as fast as possible.")
    Terminal.inst().message("\t --check-data @todo Process a test on candles data. Check if there is inconsitencies into the time of the candles and if there is some gaps. The test is done only on the defined range of time.")
    Terminal.inst().message("\t --from=<YYYY-MM-DDThh:mm:ss> define the date time from which start the backtesting, fetcher or binarizer. If ommited use whoole data set (take care).")
    Terminal.inst().message("\t --to=<YYYY-MM-DDThh:mm:ss> define the date time to which stop the backtesting, fetcher or binarizer. If ommited use now.")
    Terminal.inst().message("\t --last=<number> Fast last number of candles for every watched market (take care can take all requests credits on the broker). By default it is configured to get 1m, 5m and 1h candles.")
    Terminal.inst().message("\t --market=<market-id> Specific market identifier to fetch, binarize only.")
    Terminal.inst().message("\t --broker=<broker-name> Specific fetcher or watcher name to fetche or binarize market from.")
    Terminal.inst().message("\t --timeframe=<timeframe> Time frame unit or 0 for trade level. For fetcher, higher candles are generated. Defined value is in second or an alias in 1m 5m 15m 1h 2h 4h d m w")
    Terminal.inst().message("\t --cascaded=<max-timeframe> During fetch process generate the candles of highers timeframe from lowers. Default is no. Take care to have entire multiple to fullfill the generated candles.")
    Terminal.inst().message("\t --spec=<specific-option> Specific fetcher option (exemple STOCK for alphavantage.co fetcher to fetch a stock market).")
    Terminal.inst().message("\t --watcher-only Only watch and save market/candles data into the database. No trade and neither paper mode trades are performed.")
    Terminal.inst().message("\t --read-only Don't write market neither candles data to the database. Default is writing to the database.")
    Terminal.inst().message("\t --tool=<tool-name> Execute a specific tool @todo.")
    Terminal.inst().message("\t --fetch Process the data fetcher.")
    Terminal.inst().message("\t --binarize Process to text file to binary conversion for a market.")
    Terminal.inst().message("\t --sync Process a synchronization of the watched market from a particular broker.")
    Terminal.inst().message("")
    Terminal.inst().message("\t During usage press ':h<ENTER>' to get interative commands help. Press ':q<ENTER>' to exit. Knows issues can lock one ore more thread, then you will need to kill the process yourself.")
    Terminal.inst().message("")


def display_welcome():
    Terminal.inst().action("To type a command line, start with a ':', finally validate by <ENTER> or cancel with <ESC>.", view='content')
    Terminal.inst().action("Enter command :help or :h for command details, and :quit :q to exit", view='content')

    # @todo an ASCII art centered SIIS title
