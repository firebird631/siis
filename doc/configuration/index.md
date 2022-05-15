# Global and user configuration #

Each json file of the config directory could be overridden by adding your own copy of the file in your local _siis/config_
directory. Every parameter can be overridden, and new entries can be inserted, but never modify the original files.

Default and user customisable files :

* databases.json : Databases configuration, you have to override if you change the defaults
* indicators.json : Supported technicals indicators, if you create your own you will have to override this file
* regions.json : Supported regions, if you create your own you will have to override this file
* tradeops.json : Supported trade operations, if you create your own you will have to override this file
* fetchers.json : Supported fetchers, if you create your own you will have to override this file

Each of these files exists in the source code of SiiS. The default parameters would suffice except
databases.json and monitoring.json.

User only files :
* identities.json : Your account API-key goes here
* monitoring.json : Monitoring service configuration, you must override it, and recreate your api-key
* profiles/\*.json : Configured strategies, you have to configure at least one profile

If you use another database than PostgreSQL or another username or password than siis/siis you will
have to override this file.

You need to create an identities.json file and at least one profile of strategy to run the bot.

List of the subdirectories of config :

* watchers/ : One file per watcher to configure, name of file must refer to a valid watcher name
* traders/ : One file per trader to configure, name of file must refer to a valid trader name
* profiles/ : One file per profile to configure
* notifiers/ : One file per notifier to configure

## Database ##

### config/databases.json ###

The 'siis' database configuration (type is pgsql or mysql). There is only one database for now.

## Identities ##

### config/identities.json ###

This is the more sensible file, which contains your API-keys.
You have a config/identity.json.template file. Do not modify this file it will not be read.

Parameters :

* key is the identifier of the exchange/trader
  * For example : binance.com, binancefutures.com, kraken.com, bitmex.com, ig.com ...
* value is a dict with another dict with :
  * key as the name of the profiles (used as first parameter of the command line to start siis.py)
  * value with :
      * "api-key": Value of your API-key
      * "api-secret": Value of your API-secret
        * Used for Binance Spot and Futures, Kraken Spot and BitMex
      * "host": url of the exchange
        * for Binance Spot : binance.com
        * for Binance Futures : binance.com
        * for BitMex : www.bitmex.com
        * for BitMex Testnet : testnet.bitmex.com
        * for Kraken Spot : api.kraken.com
        * for IG CFD : api.ig.com
        * for IG CFD demo : demo-api.ig.com
      * some others values are specific :
        * for Kraken Spot :
          * @todo
        * for IG CFD :
          * "username": Connection username
          * "password": Connection password
          * "account-id": User account identifier (with letters and digits)
          * "timezone": 1
          * "encryption": true
        * for Binance Spot, Binance Futures and Kraken Spot :
          * "account-id": User specified unique account identifier used for display and database storage and reports

The template show you the needed values to configure for the supported plateform.

## Monitoring ##

### config/monitoring.json ###

Contains the configuration of the listening service to connect a future Web tools to control SiiS more friendly than using the CLI.

## Indicators ##

@todo

## Regions ##

@todo

## Trade Operations ##

@todo

## Fetchers ##

@todo

## Watchers ##

### config/watchers/ ###

The default configuration might suffice, and you can override most of the parameters into your profiles.

There is one configuration per exchange to have the capacity to connect to a broker, watching price data, and user trade data.
The values could be overridden per appliance, here it's the general settings.

Parameters :
* status if None then it will not be loaded by default else must be set to 'load'
* classpath You should not modify the default value
* symbols The list of the market identifier that you want to look for
    * (could be overridden per appliance profile)
    * on Binance all tickers are watched, but you can filter for some markets
    * on Bitmex all markets are subscribed by default, but you can filter too
    * on IG take care because you are limited on the number of subscriptions (like 40 max per account)
    * this must be a list of string
        * either the full name of the market
        * either a wildcard prefixed value. For example *BTC to filter any BTC quoted pairs
        * either a ! prefixed value (meaning not) for avoiding this particular market
        * you could have ['*BTC', '!BCHABCBTC'] for example to watching any BTC quote pairs excepted the BCHABCBTC.
* there is some more specific options on the tradingview webhook server (host and port of your listening server).

## Traders ##

### config/traders/ ###

The default configuration might suffice, and you can override most of the parameters into your profiles.

There is one entry per broker to have the capacity to enable the trading feature for the live-mode.
The values could be overridden per appliance, here it's the general settings.

Parameters :

* status if None then it will not be loaded by default else must be set to 'load'
    * (could be overridden per appliance profile)
* classpath You should not modify the default value
* symbols contain a list of the market identifiers allowed for trading and then strategies will be able to auto-trades
    * (could be overridden per appliance profile)
    * If a market identifier is not defined on the WATCHERS side it could not be found
* paper-mode To define the paper trader initially balances
    * (could be overridden per appliance profile)
    * type asset or margin to specify the account type
    * currency principal currency asset symbol
    * currency-symbol only for display
    * alt-currency alternative currency asset symbol (useful for Binance)
    * alt-currency-symbol only for display
    * initial balance in the currency if type is margin
    * assets is a list of the initials balance for different assets
        * base name of the asset
        * quote preferred quote (where asset + quote must be related to a valid market)
        * initial quantity for the asset

## Profiles ##

You must define one file per profile, the name of the file act as the name of reference.
This is the profile name to used on the command line options --profiles=\<profilename>. without the .json extension.

#### config/profiles/ ####

Content of a such file :

* "watchers" A dict of the watchers to use
    * "name": unique name of the watcher to connect
    * status Must be set to enabled to load the module of the watcher
    * symbols If defined here it overrides the symbols list from config.py (see WATCHERS)
    * ...
* "trader"
    * "name": name of the trader/exchange to trade on (binance.com, bitmex.com, ig.com...)
    * any of the options configured in the config.py TRADERS can be overridden here 
    * especially the paper-mode option when you want to make some specifics profiles of backtesting
    * instruments A dict for the mapping of the traded instruments
    * Supports a wildcard as the beginning
    * You can map a common symbol name (like EURUSD) to the broker market identifier (useful when multiple watcher sources)
    * market-id Mapped broker unique market identifier or {0} when using wildcard
        * If you have for example '\*BTC' as instrument, you want to map any of the BTC quote market to the same settings
          then you will have to set market-id to {0} that will be replaced by the filtered market identifier
    * size Base quantity in quote asset to trade
        * if USD 100 and margin, will trade 100$ per position
        * if BTC 0.5 and asset spot, will trade an equivalent (adjusted value) of 0.5 BTC of the asset quantity
        * if size is in contract then 1.0 mean 1 contract (1 lot for forex, or 1 mini-lot if market is mini lot or 1 micro-lot...)
* alias User defined instrument name alias
  * ... 
* "strategy" :
    * "name": Identifier of the strategy (binance.com, bitmex.com, ig.com....)
    * "id": 
    * "parameters": Here you can override any of the default strategy parameters (indicator constants, timeframes...)
      * "market-type": 
      * "region-allow": 
      * "min-vol24h": 
      * "min-price": 
      * "allow-short": 
      * "max-trades": 
      * "timeframes": A dict of the configured timeframes
        * key is the local name
        * value is a dict with :
          * "timeframe": code of the timeframe (1m, 5m, 1h, 1d...)
          * "mode": 
          * "depth" :
          * "history": 
          * "signal-at-close": 
          * "indicators" is a dict for each configured indicators :
            * key is the name of the indicator
            * value is an array with the parameters specific to the indicator
      * the others values are per strategy specifics
        * can be a single value
        * or a dict for the contexts
* "notifiers": A dict of the notifiers to use
  * the key is used to name your notifier, to enable/disable or modify some options during runtime
  * the value is a dict with :
    * "status": 
    * "name": 
    * the others values are per notifier specifics
