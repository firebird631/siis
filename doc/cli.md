# Command Line Interface #

There is three sort of commands, on the terminal shell and 2 on the program terminal instance (default and command mode).

## Command Line Arguments ##

```
python siis.py <identity> [--help, --options...]
```

[Those options are explained into the general README.md.](/README.md)


## Program terminal instance ##

Once started you could leave using the command ":q"\<enter-key>.

There is a default mode, with some keys are bound to some fonctions, lower case and upper case letters, and digits,
plus the arrows, shift arrows, and special case for the hjkl keys.

The command mode begin when you tip a semicolumn ":" character.


### Default mode ###

Global fonctions are accessible throught direct keys :
* changing the active view
* clearing the console or signal or debug view content
* toggle on the desktop notifier (popup and audio alerts)
* global state


### Command mode ###

More specifics functions are obtained using the commande mode :
* appliance management (only of what is possible to modify)
* trader info, control and strategy info, control
* trade info and trade operations
* region mangement and region info
* charting
* aliases


### Views ###

There is differents views, accessibles using actions keys.
On a view you can using the page-up and page-down keys to scroll per page,
or using a Shift+(Arrow-key) (left and right scroll by 1 column, up and down by 1 row).

The Shift+Page-Up and Shift+Page-Down allow to change the displayed strategy appliance.

The h,j,k and l key in default modes acts like the Shift+(Arrow-key). Some SSH client does not
correctly map Shit+(Arrow-key), then its a usefull alternative.

There are multiples regions :

![View regions](/doc/img/viewareas1.png)


#### Content region ###

The 4 rows area in the bottom of the screen, upside of the notifier and the command line,
defined the content message view.

All important message goes here, like a disconnection, or a major error.


#### Right pane ####

Unused, but reserved for later usage, like to display the order book.


#### Console view ####

This is the initially displayed view, accessible throught the Shift+I shortcut.
All logged message goes to this view, you can scroll using shift+arrow and page-up/down keys.

By default it always auto-scroll to the last message.

Errors, warning, message, results of an interactive command goes here.

You can clear its content using Shift+C shortcut.


#### Debug view ####

This is where the developper debug message goes, accessible throught the Shift+D shortcut.
All logged message goes to this view, you can scroll using shift+arrow and page-up/down keys.

By default it always auto-scroll to the last message.

This is a special view, normally only using on developpment stage of a strategy.

You can clear its content using Shift+C shortcut.


#### Signal view ####

This is where the generated strategies/appliances signals goes, accessible throught the Shift+N shortcut.

* Generated signal or trade are catched by this view, the last 200 only are visibles.
* Each signal has a hash color
* The order is from oldest to the most recent
* The comma key ',' allow to group signal entry and exit

![Signals view](/doc/img/signalsview1.png)

...


#### Markets view ####

This display the status and details of the markets, accessible throught the Shift+M shortcut.

![Markets view](/doc/img/marketsview1.png)

...


#### Tickers view ####

This display tickers of the markets, accessible throught the Shift+T shortcut.

![Tickers view](/doc/img/tickersview1.png)

...


#### Account view ####

This display accounts details like balance, margins, unrealized P/L are visibles, accessible throught the Shift+A shortcut.

![Accounts view](/doc/img/accountsview1.png)

...


#### Asset view ####

This display assets balances, free, locked, total, unrealized P/L are visibles, accessible throught the Shift+Q shortcut.

![Assets view](/doc/img/accountsview1.png)

...


#### Active trades view ####

This display current active, valid or pending trades for the current strategy, accessible throught the Shift+F shortcut.

The current displayed strategy/appliance can be switched using the Shift+Page-Up/Page-Down shortcuts.

![Active trades view](/doc/img/activetradesview1.png)

...


#### History trades view ####

This display history of realized trades for the current strategy, accessible throught the Shift+S shortcut.

The current displayed strategy/appliance can be switched using the Shift+Page-Up/Page-Down shortcuts.

![Trades history view](/doc/img/tradeshistoryview1.png)

...


#### Performance/resume view ####

This display sums of the differents trades per market and the total for the current strategy, accessible throught the Shift+P shortcut.

The current displayed strategy/appliance can be switched using the Shift+Page-Up/Page-Down shortcuts.

![Performances view](/doc/img/perfsview1.png)

...


#### Order book view ####

Order book goes to the right pane.

To toggle the display of the order book use the Shift+B shortcut.

The current displayed strategy/appliance can be switched using the Shift+Page-Up/Page-Down shortcuts.
The current displayed market can be switched using the +/- shortcuts.

... to be implemented ...


#### Strategy/appliance indicators/state view ####

Each strategy/appliance have some states, the ideas is to allow any strategy to display some living data, helping the
creation of a strategy, or helping to understand the state of some signals and indicators.

The current displayed strategy/appliance can be switched using the Shift+Page-Up/Page-Down shortcuts.
The current displayed market can be switched using the +/- shortcuts.

... to be implemented ...
