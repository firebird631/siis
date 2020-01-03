# Syncer #

The syncer tool allow to synchronize specific markets info details for a specific broker.
The synchronization is always done when starting the bot live and paper-mode but this is not done with the backtesting mode.

Then this tool could be used in some circomstances, to sync the initial or the last market info details.

The differents syncers are related to the configured and implemented watchers, then HistData or TickStory are not usable with syncer.

...
