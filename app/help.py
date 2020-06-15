# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Application help

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_LONG_NAME

from terminal.terminal import Terminal
from random import randint
from tools.tool import Tool


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
        Terminal.inst().message(" - '%' toggle table percent display", view='content')

        Terminal.inst().message(" - 'p' list positions (will be replaced by a dedicated view)", view='content')
        Terminal.inst().message(" - 'o' list orders (will be replaced by a dedicated view)", view='content')

        Terminal.inst().message(" - 'A' show account view", view='content')
        Terminal.inst().message(" - 'Q' show assets view", view='content')
        Terminal.inst().message(" - 'M' show markets view", view='content')
        Terminal.inst().message(" - 'T' show tickers view", view='content')
        Terminal.inst().message(" - 'F' show strategy view", view='content')
        Terminal.inst().message(" - 'S' show statistic view", view='content')
        Terminal.inst().message(" - 'P' show performance view", view='content')
        Terminal.inst().message(" - 'I' show console view", view='content')
        Terminal.inst().message(" - 'N' show notification/signal view", view='content')
        Terminal.inst().message(" - 'X' show positions view", view='content')
        Terminal.inst().message(" - 'O' show orders view", view='content')
        Terminal.inst().message(" - 'W' show alerts view", view='content')
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
    Terminal.inst().message("  python siis.py <identity> <--options>")
    Terminal.inst().message("")
    Terminal.inst().message("Profiles are defined in config/identities.json located at .siis local data.")
    Terminal.inst().message("")
    Terminal.inst().message("  --help display command line help.")
    Terminal.inst().message("  --version display the version number.")
    Terminal.inst().message("  --profile=<profile> Profile to instanciate.")
    Terminal.inst().message("  --paper-mode instanciate paper mode trader and simulate as best as possible.")
    Terminal.inst().message("  --backtest process a backtesting, uses paper mode traders and data history avalaible in the database.")
    Terminal.inst().message("  --timestep=<seconds> Timestep in seconds to increment the backesting.")
    Terminal.inst().message("    More precise is more accurate but need more computing simulation. Adjust to at least fits to the minimal")
    Terminal.inst().message("    candles size uses in the backtested strategies. Default is 60 seconds.")
    Terminal.inst().message("  --time-factor=<factor> in backtesting mode only allow the user to change the time factor and permit to interact")
    Terminal.inst().message("    during the backtesting. Default speed factor is as fast as possible.")
    Terminal.inst().message("  --from=<YYYY-MM-DDThh:mm:ss> define the date time from which start the backtesting, fetcher or binarizer.")
    Terminal.inst().message("    If ommited use whoole data set (take care).")
    Terminal.inst().message("  --to=<YYYY-MM-DDThh:mm:ss> define the date time to which stop the backtesting, fetcher or binarizer. If ommited use now.")
    Terminal.inst().message("  --last=<number> Fast last number of candles for every watched market (take care can take all requests credits on the broker).")
    Terminal.inst().message("    By default it is configured to get 1m, 5m and 1h candles.")
    Terminal.inst().message("  --market=<market-id> Specific market identifier to fetch, binarize only.")
    Terminal.inst().message("  --broker=<broker-name> Specific fetcher or watcher name to fetche or binarize market from.")
    Terminal.inst().message("  --timeframe=<timeframe> Time frame unit or 0 for trade level. For fetcher, higher candles are generated.")
    Terminal.inst().message("    Defined value is in second or an alias in 1m 5m 15m 1h 2h 4h d m w")
    Terminal.inst().message("  --cascaded=<max-timeframe> During fetch process generate the candles of highers timeframe from lowers.")
    Terminal.inst().message("    Default is none. Take care to have entire multiple to fullfill the generated candles.")
    Terminal.inst().message("  --spec=<specific-option> Specific fetcher option (exemple STOCK for alphavantage.co fetcher to fetch a stock market).")
    Terminal.inst().message("  --watcher-only Only watch and save market/candles data into the database. No trade and neither paper mode trades are performed.")
    Terminal.inst().message("  --initial-fetch Process the fetching of recent OHLCs when subscribing to a market. Default don't fetch.")
    Terminal.inst().message("  --store-ohlc Write OHLCs to DB. Default not stored.")
    Terminal.inst().message("  --store-trade Write tick/trade/quote to filesystem. Default not stored.")
    Terminal.inst().message("")
    Terminal.inst().message("Tools :")
    Terminal.inst().message("  --tool=<tool-name> Execute a specific tool.")
    Terminal.inst().message("")
    display_help_tools()
    # @todo after replaced any tools by theirs model remove below
    Terminal.inst().message("  --fetch Process the data fetcher.")
    Terminal.inst().message("    Specify --broker, --market, --timeframe, --from and --to date. Optional : --cascaded, --from or --update.")
    Terminal.inst().message("  --binarize Process ticks/trades/quotes text file to binary conversion.")
    Terminal.inst().message("    Specify --broker, --market, --from and --to date.")
    Terminal.inst().message("  --rebuild Rebuild OHLCs from the trades/ticks/quotes file data.")
    Terminal.inst().message("    Specify --broker, --market, --timeframe, --from and --to date. Plus one of : --target or --cascaded.")
    Terminal.inst().message("  --optimize Check OHLCs consistency from the trades/ticks/quotes file data.")
    Terminal.inst().message("    Specify --broker, --market, --timeframe, --from and --to date.")
    Terminal.inst().message("  --import Import a SIIS or MT4 data set from a file.")
    Terminal.inst().message("    For MT4 specify --broker, --market, --timeframe, --from and --to date. Optional --zip.")
    Terminal.inst().message("  --export Export a data set to a SIIS file format.")
    Terminal.inst().message("    Specify --broker, --market, --from and --to date. Optional --timeframe else any.")
    Terminal.inst().message("  --clean Remove some data from the database.")
    Terminal.inst().message("    Specify --broker. Optional : --market, --from and --to date, --timeframe, --objects.")
    Terminal.inst().message("")
    Terminal.inst().message("During usage press ':h<ENTER>' to get interative commands help. Press ':q<ENTER>' to exit.")
    Terminal.inst().message("")


def display_help_tools():
    tools = Tool.find_tools()

    for tool in tools:
        try:
            alias, msgs = Tool.tool_help(tool)

            if alias:
                Terminal.inst().message("  --tool=%s, --%s %s" % (tool, alias, msgs[0] if len(msgs) > 0 else ""))
            else:
                Terminal.inst().message("  --tool=%s %s" % (tool, msgs[0] if len(msgs) > 0 else ""))

            for msg in msgs[1:]:
                Terminal.inst().message("    " + msg)
        except:
            pass


def display_welcome():
    Terminal.inst().info("Console", view='content-head')
    
    Terminal.inst().action("To type a command line, start with a ':', finally validate by <ENTER> or cancel with <ESC>.", view='content')
    Terminal.inst().action("Enter command :help or :h for command details, and :quit :q to exit", view='content')

    LOGO1 = """
   SSSSSSSSSSSSSSS IIIIIIIIIIIIIIIIIIII   SSSSSSSSSSSSSSS 
 SS:::::::::::::::SI::::::::II::::::::I SS:::::::::::::::S
S:::::SSSSSS::::::SI::::::::II::::::::IS:::::SSSSSS::::::S
S:::::S     SSSSSSSII::::::IIII::::::IIS:::::S     SSSSSSS
S:::::S              I::::I    I::::I  S:::::S            
S:::::S              I::::I    I::::I  S:::::S            
 S::::SSSS           I::::I    I::::I   S::::SSSS         
  SS::::::SSSSS      I::::I    I::::I    SS::::::SSSSS    
    SSS::::::::SS    I::::I    I::::I      SSS::::::::SS  
       SSSSSS::::S   I::::I    I::::I         SSSSSS::::S 
            S:::::S  I::::I    I::::I              S:::::S
            S:::::S  I::::I    I::::I              S:::::S
SSSSSSS     S:::::SII::::::IIII::::::IISSSSSSS     S:::::S
S::::::SSSSSS:::::SI::::::::II::::::::IS::::::SSSSSS:::::S
S:::::::::::::::SS I::::::::II::::::::IS:::::::::::::::SS 
 SSSSSSSSSSSSSSS   IIIIIIIIIIIIIIIIIIII SSSSSSSSSSSSSSS"""

    LOGO2 = """
   ▄████████  ▄█   ▄█     ▄████████ 
  ███    ███ ███  ███    ███    ███ 
  ███    █▀  ███▌ ███▌   ███    █▀  
  ███        ███▌ ███▌   ███        
▀███████████ ███▌ ███▌ ▀███████████ 
         ███ ███  ███           ███ 
   ▄█    ███ ███  ███     ▄█    ███ 
 ▄████████▀  █▀   █▀    ▄████████▀"""

    # ASCII art centered SIIS title
    logo = LOGO1 if randint(0, 10) < 5 else LOGO2
    Terminal.inst().message(logo, view="content")
