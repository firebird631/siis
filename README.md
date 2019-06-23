SIIS Strategy/Scalper Indicator Information System
==================================================

**The redaction of this document is in progress.**

Abstract
--------

SiiS is a autotrading bot for forex, indices and crypto currencies markets.
It also support semi-automated trading in way to manage your entry and exits
with more possibilities than an exchanges allow.

This version is more a functionnal prototype than a final professional trading tool.
It is developped in Python3, using TA-lib, numpy and matplotlib for the basic charting client.

A more performant, but still in developpement, SiiS revisited is available at [github:siis-rev](https://github.com/dream-overflow/siis-rev)


Features
--------

* Initially developped for Linux, but should work on Window or MacOSX
* Traditionnals and crypto markets brokers (traders) are supported
    * Binance
    * Bitmex
    * IG
    * 1broker (obsolete)
* Some others data-source in way to gets prices/volumes data
   * HistData (only to import manually downloaded files)
   * AlphaVantage (WIP)
   * Tiingo (WIP)
* Fetching OHLC and ticks history data in PostgreSQL or MySQL DB
* Multiple instance can run at the same time
* Many strategies and markets can run on a same instance (test with 100+ markets on a single instance)
* Connection with API key (open-source you can check than yours API keys are safe with SiiS)
* Configuration of multiple accounts identities
* Configuration of multiple profiles and appliances (an appliance is a context of a strategy)
    * Combine one or more appliance to a profiles
    * Configure multiple appliances and profiles with different options
* Backtesting
* Paper-mode (simulate a broker for spot and margin)
* Live-mode trading on your broker account
* Interactive command lien interface
    * Backtesting with a slow down or real time factor allowing you to replay an history
      and doing manual and semi-automated trading
* Try as possible to take-care of the spread of the market and the commissions
* Compute the average unit price of owned assets on Binance
* Display account detail and assets quantities
* Display tickers and markets informations
* Display per strategy current (active or pending) trades, trades history and performance
* Manage multiple timeframe
* Common indicators are supported (RSI, SMA, BBANDS, ATR...)
* Pure signal strategies are possibles in way to only generating some signal
* Desktop notification on Linux via dbus
* Audible notification on Linux via aplay
* Basic Discord WebHook notifier (have to be redone)
* 3 initials strategies (1 for bitcoin/etherum, 1 for forex, 1 for majors altcoins)
* WebHook of TradingView strategies with an example of a such strategy (need an extra JS plugin on the browser)
* SocialCopy capacities (deprecated for now, was done initially on 1broker, some works have to be redone)
* Manual per trade directive (more directive will be coming)
* Manual regions of interest per market strategy to help the bot filtering some signals (WIP)
    * Range region
    * Trend channel region

### Donation ###

* BTC: 1GVdwcVrvvbqBgzNMii6tGNhTYnGvsJZFE
* ETH: 0xd9cbda09703cdd4df9aeabf63f23be8da19ca9bf


Installation
------------

Need Python3.6 or Python3.7 on your system.
Tested on Debian, Ubuntu and Fedora.

### Create a PIP virtual env ###

```
python -m venv siis.venv
source siis.venv/bin/activate
```

You need to active it each time you open your terminal before running SiiS.

From deps/ directory, first install TA-Lib :

```
tar xvzf deps/ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure
make
```

```
sudo make install
```

copy the content of the include folder into siis.venv/include/ta-lib/
and copy the .a and .so to siis.venv/lib/pythonX.Y/site-packages


### Python dependencies ###

pip install -r requirements.txt


Before running the lib folder containing TA-Lib must be in the LD_LIBRARY_PATH :

With, if installed in the default directory :

export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH


### Database ###

Prefers the PostgreSQL database server. For now SiiS does not bulk data insert, the performance
with PostgreSQL are OK, but lesser on MySQL.

The sql/ directory contains the SQL script for the two databases and the first line of comment
in these files describe a possible way to install them.


Configuration
-------------

First running will try to create a data structure on your local user.
* /home/<username>/.siis on Linux based systems
* C:\Users\<username\AppData\Local\siis on Windows
* /Users/<username>/.siis on MacOSX

The directory will contains 4 sub-directories:

* config/ contains important configurations files (described belows)
* log/ contains siis.log the main log and evantually some others logs files (client.log...)
* markets/ contains sub-directories for each configured brokers (detailes belows)
* reports/ contains the reports of the backtesting, per datetime, broker name, 3 files per reports (data.py, report.log, trades.log)

### config ###

#### <.siis/config/>config.py ####

You have an initial file in config/config.py. Do not modifiy the original.

This file comes from the beginning of the project, would need some reorganization, but it looks like :

* DATABASES the 'siis' database configuration (type is pgsql or mysql). There is only only database for now.
* FETCHERS You should not modifiy this dict, it contains the classpath for the availables fetchers.
* WATCHERS Must contain 1 entry per broker to have the capacity to connect to a broker, watching price data, and user trade data
    * Not those values could be overrided into the appliances.py file but here you could defined the general config
        and eventually having the necessary adjustement on the appliances profiles
    * status if None then it will not be loaded by default else must be set to 'load'
    * classpath You should not modify the default value
    * symbols The list of the market identifier that you want to look for
        * (could be overrided per appliance profile)
        * on binance all tickers are watched but you can filter for some markets
        * on bitmex all markets are subscribed by default but you can filter too
        * on IG take care because your are limit on the number of subscriptions (like 40 max per account)
        * this must be a list of string
            * either the full name of the market
            * either a wildchar prefixed value. For example *BTC to filter any BTC quoted paires
            * either a ! prefixed value (meaning not) for avoiding this particular market
            * you could have ['*BTC', '!BCHABCBTC'] for exemple to watching any BTC quote paires excpted the BCHABCBTC.
    * there is some more specific options on the tradingview webhock server (host and port of your listening server).
* INDICATORS Like for fetcher you might not have to modifiy this part or if you create your own indicators.
* TRADEOPS Again likes indictors, except if you create your own trade operations.
* STRATEGIES Contains the default built-ins strategies, you'll need to add yours here.
* TRADERS Must contains 1 entry per broker to have the capacity to enable the trading feature for the live-mode
    * Not those values could be overrided into the appliances.py file but here you could defined the general config
        and eventually having the necessary adjustement on the appliances profiles
    * status if None then it will not be loaded by default else must be set to 'load'
        * (could be overrided per appliance profile)
    * classpath You should not modify the default value
    * symbols Contains a list of the market identifiers allowed for trading and than strategies will be able to auto-trades
        * (could be overrided per appliance profile)
        * If a market identifier is not defined on the WATCHERS side it could not be found
    * leverage its a deprecated values list used only for 1broker
        * (could be overrided per appliance profile)
    * stop-loosing-position its a deprecated feature to cut margin positions at the trader level
        * (could be overrided per appliance profile)
        * mode level or percent or balance-percent
        * value
    * paper-mode To define the paper trader initially balances
        * (could be overrided per appliance profile)
        * type asset or margin to specify the account type
        * currency principal currency asset symbol
        * currency-symbol only for display
        * alt-currency alternative currency asset symbol (usefull for binance)
        * alt-currency-symbol only for display
        * initial initial balance in the currency if type is margin
        * assets is a list of the initials balance for different assets
            * base name of the asset
            * quote prefered quote (where asset + quote must related to a valid market)
            * initial initial quantity for the asset

* MONITORING Contains the configuration of the listening service to connect a futur Web tools
  to control SiiS more friendly than using the CLI


#### <.siis/config/>appliances.py ####

You have an initial file in config/appliances.py. Do not modify the original.

This file must contains your configuration named profile (command line options --profile=<profilename>).
You have the profiles and the appliances.

A profile is a mixing of one or many appliance, that can be runned on a same instance of SiiS, with
traders and watchers options overriding.

* PROFILES At the first level you have the unique name of the profile
    * If no profile is specicied on command line option the default profile will be used
        * You should constat than any appliances will then be loaded, its a bad idea, probably the profile option
          will be mandatory in the futur and the wildchar usage too.
    * appliances A list of the name of the appliance to run in this profile (instance)
    * watchers A dict of the watchers to enable
        * unique name of the watcher
            * status Must be set to enabled to load the module of the watcher
    * traders a dict of the traders to enable
        * unique name of the trader
            * it is recommanded to have only one trader per profile (per running instance)
            * any of the options configured in the config.py TRADERS can be overrided here
              especially the paper-mode option when you want to make some specifics profiles of backtesting
* APPLIANCES At the first level you have the unique name of the appliance
    * status enabled or None If None the appliance could not be started in any of the profiles
    * strategy
        * name Identifier of the strategy (binance.com, bitmex.com, ig.com....)
        * parameters Here you can overrides any of the default strategy parameters (indicator constants, timeframes...)
    * watcher A list of the different watcher to use for the strategy (for now only one source of data is possible)
        * name Watcher unique identifier
        * symbols If defined here it overrided the symbols list from config.py (see WATCHERS)
    * trader The related trader (even for paper-mode)
        * name Identifier of the trader (binance.com, bitmex.com, ig.com...)
        * instruments A dict for the mapping of the traded instruments
            * Supports a wildchar as the beginning
            * You can map a common symbol name (like EURUSD) to the broker market identifier (useful when multiple watcher sources)
            * market-id Mapped broker unique market identifier or {0} when using wildchar
                * If you have for example '*BTC' as instrument, you want to map any of the BTC quote market to the same settings
                  then you will have to set market-id to {0} that will be replaced by the filtered market identifier
            * size Base quantity in quote asset to trade
                * if USD 100 and margin, will trade 100$ per position
                * if BTC 0.5 and asset spot, will trade an equivalent (adjusted value) of 0.5 BTC of the asset quantity
                * if size is in contract then 1.0 mean 1 contract (1 lot for forex, or 1 mini-lot if market is mini lot or 1 micro-lot...)
            * alias User defined instrument name alias
 

#### <.siis/config/>identities.py ####

This is the more sensible file, which contains your API keys.
You have a config/identities.py.template file. Do not modify this file it will not be read.

* IDENTITIES
    * the identifier of the differents brokers
        * profiles name
            * for my usage I have real and demo
            * specific needed value for the connector (API key, account identifier, password...)

The template show you the needed values to configure for the supported brokers.


### markets ###

Each broker have its own usage name, creating if directory. Then you have 1 sub-directory per market.
The market is identified by the unique broker market name.

Then you will have a sub-directory T/ meaning tick or trade. All filed then found defines data at the tick
or trade level. For binance or bitmex this is at aggregate trade level, for IG its ticks.

There is one file per month, there is a binary and a tabular version of the file at this time. But maybe later
the tabular version will be disabled and not stored by default.

See more details on the data fetching section.


### reports ###

Each backtest generate a triplet of files beginning with the starting datetime of the backtest, plus 
the related broker identifier, and suffixed by :

* data.py some Python data array (possibles evolution of this file)
* report.log this is a summary
* trades.log this a tabular file containing each trades with profit/loss and balance


Running
-------

python siis.py <identity> [--help, --options...]


Importing some data
-------------------

...


Backtesting
-----------

...


Paper-mode
----------

...


Live-mode
---------

...


Data storage
------------

...


## Data fetching ##

...


Troubles
--------

TA-lib is not found : look you have installed it, and may be you have to export your LD_LIBRARY_PATH.


Disclaimer
----------

The authors are not responsible of the losses on your trading accounts you will made using SiiS Revisited,
nethier of the data loss, corruption, computer crash or physicial dommages on your computers or on the cloud you uses.

The authors are not responsible of the loss due to the lack of the security of your systems.

Use SiiS at your own risk, backtest strategies many time before running them on a live account. Test the stability,
test the efficiency, take in account the potential execution slippage and latency caused by the network, the broker or
by having an inadequate system.

