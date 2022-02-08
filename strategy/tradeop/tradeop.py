# @date 2019-06-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy trade operation base class.
import traceback

from trader.trader import Trader

from strategy.strategytrade import StrategyTrade
from strategy.strategytrader import StrategyTrader

from trader.order import Order

import logging
logger = logging.getLogger('siis.strategy.tradeop')
error_logger = logging.getLogger('siis.error.strategy.tradeop')
traceback_logger = logging.getLogger('siis.traceback.strategy.tradeop')


class TradeOp(object):
    """
    Strategy trade operation base class.
    """

    VERSION = "1.0.0"

    OP_UNDEFINED = 0
    OP_STEP_STOP_LOSS = 1
    OP_SINGLE_VAR_CONDITION = 2
    OP_TWO_VARS_CONDITION = 3

    STAGE_ENTRY = 1
    STAGE_EXIT = -1

    OP = -1
    NAME = "undefined"

    def __init__(self, stage):
        self._id = -1        # operation unique identifier
        self._stage = stage  # apply on entry or exit
        self._count = -1     # persistent operation count is -1, else its value is decremented until 0

    #
    # getters
    #

    @classmethod
    def name(cls):
        return cls.NAME

    @classmethod
    def op(cls):
        return cls.OP

    @classmethod
    def version(cls):
        return cls.VERSION

    @property
    def id(self):
        return self._id

    @property
    def count(self):
        return self._count

    @property
    def is_persistent(self):
        return self._count < 0

    @property
    def stage(self):
        return self._stage

    #
    # setters
    #

    def set_id(self, _id: int):
        self._id = _id

    def init(self, parameters: dict):
        """
        Override this method to setup operation parameters from the parameters dict.
        """
        pass

    #
    # processing
    #

    def can_delete(self) -> bool:
        return self._count == 0

    def test_and_operate(self, trade: StrategyTrade, strategy_trader: StrategyTrader, trader: Trader) -> bool:
        """
        Each time the market price change perform to this test. If the test pass then
        it is executed and removed from the list or kept if its a persistent operation.

        @return True when the use counter reach zero. Meaning the operation must be removed.
        """

        # undefined trade
        if not trade:
            return False

        # check the counter
        if self._count == 0:
            return False

        if self._stage == TradeOp.STAGE_ENTRY and trade.is_active():
            # cannot be performed once the trade is active
            return True

        if self._stage == TradeOp.STAGE_EXIT and not trade.is_active():
            # cannot be performed until the trade is active
            return False

        try:
            if self.operate(trade, strategy_trader, trader):
                if self._count > 0:
                    self._count -= 1

                return self._count == 0
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        return False

    #
    # overrides
    #

    def check(self, trade: StrategyTrade) -> bool:
        """
        Perform an integrity check on the data defined to the operation and the trade.
        @return True if the check pass.
        """
        return True

    def operate(self, trade: StrategyTrade, strategy_trader: StrategyTrader, trader: Trader) -> bool:
        """
        Override this method to implement the test and the effect of the operation.
        @return True when the operation is realized one time.
        """
        return True

    def str_info(self) -> str:
        """
        Override this method to implement the single line message info of the operation.
        """
        return ""

    def parameters(self) -> dict:
        """
        Override this method and add specific parameters to be displayed into an UI or a table.
        """
        return {
            'label': "undefined",
            'name': self.name(),
            'id': self._id,
            'stage': self.stage_to_str(),
            'count': self._count
        }

    #
    # persistence
    #

    def stage_to_str(self) -> str:
        if self._stage == TradeOp.STAGE_ENTRY:
            return "entry"
        elif self._stage == TradeOp.STAGE_EXIT:
            return "exit"
        else:
            return "undefined"

    def dumps(self) -> dict:
        """
        Override this method and add specific parameters for dumps parameters for persistence model.
        """
        return {
            'version': self.version(),
            'op': self.op(),
            'id': self._id,
            'stage': self._stage,
            'count': self._count
        }

    def loads(self, data: dict):
        """
        Override this method and add specific parameters for loads parameters from persistence model.
        """
        self._id = data.get('id', -1)
        self._stage = data.get('stage', 0)  # self.stage_from_str(data.get('stage', ''))
        self._count = data.get('count', 0)


class TradeOpStepStopLoss(TradeOp):
    """
    Step stop-loss trade operation. Each time a target is reached the stop-loss is set to a specific price.
    """

    OP = TradeOp.OP_STEP_STOP_LOSS
    NAME = 'step-stop-loss'

    def __init__(self):
        super().__init__(TradeOp.STAGE_EXIT)

        self._trigger = 0.0     # if market price reach this trigger price (in the trade direction)
        self._stop_loss = 0.0   # then the stop-loss price of the trade is modified to this price
        self._count = 1         # unique usage

    def init(self, parameters: dict):
        self._trigger = parameters['trigger']
        self._stop_loss = parameters['stop-loss']
        self._count = 1

    def check(self, trade: StrategyTrade) -> bool:
        if not self._stop_loss or not self._trigger:
            # missing price
            return False

        if trade.direction > 0:
            # long stop price must be lesser than condition price
            if self._stop_loss >= self._trigger:
                return False

        if trade.direction < 0:
            # short stop price must be greater than condition price
            if self._stop_loss <= self._trigger:
                return False

        return True

    def operate(self, trade: StrategyTrade, strategy_trader: StrategyTrader, trader: Trader) -> bool:
        if trade.direction > 0:
            # long
            if strategy_trader.instrument.close_exec_price(trade.direction) >= self._trigger:
                result = strategy_trader.trade_modify_stop_loss(trade, self._stop_loss, trade.has_stop_order())
                if result <= 0:
                    return False

                return True

        elif trade.direction < 0:
            # short
            if strategy_trader.instrument.close_exec_price(trade.direction) <= self._trigger:
                result = strategy_trader.trade_modify_stop_loss(trade, self._stop_loss, trade.has_stop_order())
                if result <= 0:
                    return False

                return True

        return False

    def str_info(self):
        return "Step stop-loss at %s when reach %s" % (self._stop_loss, self._trigger)

    def parameters(self) -> dict:
        return {
            'label': "Step stop-loss",
            'name': self.name(),
            'id': self.id,
            'stop-loss': self._stop_loss,
            'trigger': self._trigger
        }

    def dumps(self) -> dict:
        data = super().dumps()

        data['trigger'] = self._trigger
        data['stop-loss'] = self._stop_loss

        return data

    def loads(self, data: dict):
        super().loads(data)

        self._trigger = data.get('trigger', 0.0)
        self._stop_loss = data.get('stop-loss', 0.0)


class TradeSingleVarOpCondStopLoss(TradeOp):
    """
    Modify the stop-loss when a condition is true.

    @todo test for example RSI greater than... two values cross...
    """

    COND_EQ = 1
    COND_GT = 2
    COND_GTE = 3
    COND_LT = 4
    COND_LTE = 5

    OP = TradeOp.OP_SINGLE_VAR_CONDITION
    NAME = '1var-cond-stop-loss'

    def __init__(self, condition, variable):
        super().__init__(TradeOp.STAGE_EXIT)

        self._count = 1
        self._variable = variable

    def init(self, parameters: dict):
        self._count = 1

    def str_info(self) -> str:
        return "Single variable conditioned stop-loss ...@todo"

    def parameters(self) -> dict:
        return {
            'label': "Single variable conditioned stop-loss",
            'name': self.name(),
            'id': self.id,
            'variable': self._variable,
        }

    def dumps(self) -> dict:
        data = super().dumps()

        data['variable'] = self._variable

        return data

    def loads(self, data: dict):
        super().loads(data)

        self._variable = data.get('variable', 0.0)


class TradeTwoVarsOpCondStopLoss(TradeOp):
    """
    Modify the stop-loss when a condition is true.

    @todo test for example price cross ema, ema1 greater than ema2...
    """

    COND_EQ = 1
    COND_GT = 2
    COND_GTE = 3
    COND_LT = 4
    COND_LTE = 5
    COND_CROSS = 6
    
    OP = TradeOp.OP_TWO_VARS_CONDITION
    NAME = '2vars-cond-stop-loss'

    def __init__(self, condition, variable):
        super().__init__(TradeOp.STAGE_EXIT)

        self._count = 1
        self._variable = variable

    def init(self, parameters: dict):
        self._count = 1

    def str_info(self) -> str:
        return "Two variables conditioned stop-loss ...@todo"

    def parameters(self) -> dict:
        return {
            'label': "Two variables conditioned stop-loss",
            'name': self.name(),
            'id': self.id,
            # ...
        }

    def dumps(self) -> dict:
        data = super().dumps()

        data['variable'] = self._variable

        return data

    def loads(self, data: dict):
        super().loads(data)

        self._variable = data.get('variable', 0.0)
