"""
Paper Trading / Mock Execution Layer
====================================
Simulates live trading without real money for strategy testing.

This is a MOCK implementation for development and testing.
For real trading, integrate with broker APIs (Alpaca, IBKR, etc.)
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import uuid

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class Order:
    """Represents a trading order."""
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None
        }


@dataclass
class Position:
    """Represents a portfolio position."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl
        }


@dataclass
class Account:
    """Represents the trading account."""
    cash: float
    initial_capital: float
    buying_power: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    
    @property
    def equity(self) -> float:
        position_value = sum(p.market_value for p in self.positions.values())
        return self.cash + position_value
    
    @property
    def total_pnl(self) -> float:
        return self.equity - self.initial_capital
    
    @property
    def return_pct(self) -> float:
        return (self.equity / self.initial_capital) - 1
    
    def to_dict(self) -> dict:
        return {
            'cash': self.cash,
            'equity': self.equity,
            'buying_power': self.buying_power,
            'initial_capital': self.initial_capital,
            'total_pnl': self.total_pnl,
            'return_pct': self.return_pct,
            'positions': {k: v.to_dict() for k, v in self.positions.items()}
        }


class MockBroker:
    """
    Mock broker for paper trading.
    
    Simulates order execution with configurable slippage and latency.
    """
    
    def __init__(
        self,
        slippage: float = 0.0005,  # 0.05%
        commission: float = 0.0,   # $0 commission
        latency_ms: int = 50       # 50ms execution latency
    ):
        self.slippage = slippage
        self.commission = commission
        self.latency_ms = latency_ms
        self._price_feed: Dict[str, float] = {}
        
    def set_price(self, symbol: str, price: float):
        """Set current price for a symbol (for simulation)."""
        self._price_feed[symbol] = price
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        return self._price_feed.get(symbol)
    
    async def execute_order(self, order: Order) -> Order:
        """
        Execute an order with simulated slippage and latency.
        
        Returns the updated order with fill information.
        """
        # Simulate network latency
        await asyncio.sleep(self.latency_ms / 1000)
        
        # Get current price
        price = self.get_price(order.symbol)
        if price is None:
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order {order.id} rejected: No price for {order.symbol}")
            return order
        
        # Check order type conditions
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and price > order.limit_price:
                # Limit buy not triggered
                return order
            if order.side == OrderSide.SELL and price < order.limit_price:
                # Limit sell not triggered
                return order
            price = order.limit_price
        
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and price < order.stop_price:
                # Stop buy not triggered
                return order
            if order.side == OrderSide.SELL and price > order.stop_price:
                # Stop sell not triggered
                return order
        
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = price * (1 + self.slippage)
        else:
            fill_price = price * (1 - self.slippage)
        
        # Fill the order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.filled_at = datetime.now()
        
        logger.info(f"Order {order.id} filled: {order.side.value} {order.quantity} {order.symbol} @ ${fill_price:.2f}")
        
        return order


class PaperTrader:
    """
    Paper trading engine for live strategy simulation.
    
    Usage:
        trader = PaperTrader(initial_capital=100000)
        
        # Subscribe to price updates
        trader.on_fill(my_fill_handler)
        
        # Submit orders
        order = await trader.submit_order(
            symbol='AAPL',
            side=OrderSide.BUY,
            quantity=100
        )
        
        # Update prices (simulate market data)
        await trader.update_price('AAPL', 175.50)
        
        # Check account
        print(trader.account.to_dict())
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        broker: Optional[MockBroker] = None
    ):
        self.broker = broker or MockBroker()
        self.account = Account(
            cash=initial_capital,
            initial_capital=initial_capital,
            buying_power=initial_capital
        )
        self._orders: Dict[str, Order] = {}
        self._pending_orders: List[Order] = []
        self._fill_callbacks: List[Callable] = []
        self._running = False
    
    def on_fill(self, callback: Callable[[Order], None]):
        """Register a callback for order fills."""
        self._fill_callbacks.append(callback)
    
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """
        Submit a new order.
        
        Returns the order with updated status.
        """
        order_id = str(uuid.uuid4())[:8]
        
        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status=OrderStatus.SUBMITTED
        )
        
        self._orders[order_id] = order
        
        # Validate order
        if not self._validate_order(order):
            order.status = OrderStatus.REJECTED
            return order
        
        # For market orders, execute immediately
        if order_type == OrderType.MARKET:
            order = await self._execute_order(order)
        else:
            # Add to pending orders for later execution
            self._pending_orders.append(order)
        
        return order
    
    def _validate_order(self, order: Order) -> bool:
        """Validate an order before execution."""
        if order.quantity <= 0:
            logger.warning(f"Invalid order quantity: {order.quantity}")
            return False
        
        if order.side == OrderSide.BUY:
            price = self.broker.get_price(order.symbol) or 0
            required_cash = order.quantity * price * 1.01  # 1% buffer
            if required_cash > self.account.cash:
                logger.warning(f"Insufficient cash: need ${required_cash:.2f}, have ${self.account.cash:.2f}")
                return False
        
        elif order.side == OrderSide.SELL:
            position = self.account.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                logger.warning(f"Insufficient position to sell: {order.symbol}")
                return False
        
        return True
    
    async def _execute_order(self, order: Order) -> Order:
        """Execute an order through the broker."""
        order = await self.broker.execute_order(order)
        
        if order.status == OrderStatus.FILLED:
            self._update_position(order)
            self._notify_fill(order)
        
        return order
    
    def _update_position(self, order: Order):
        """Update position after order fill."""
        symbol = order.symbol
        fill_price = order.filled_price
        fill_qty = order.filled_quantity
        
        # Get or create position
        position = self.account.positions.get(symbol)
        if position is None:
            position = Position(symbol=symbol, quantity=0, avg_cost=0)
            self.account.positions[symbol] = position
        
        if order.side == OrderSide.BUY:
            # Update average cost
            total_cost = (position.quantity * position.avg_cost) + (fill_qty * fill_price)
            position.quantity += fill_qty
            if position.quantity > 0:
                position.avg_cost = total_cost / position.quantity
            
            # Deduct cash
            self.account.cash -= fill_qty * fill_price
            
        elif order.side == OrderSide.SELL:
            # Calculate realized P&L
            pnl = fill_qty * (fill_price - position.avg_cost)
            position.realized_pnl += pnl
            position.quantity -= fill_qty
            
            # Add cash
            self.account.cash += fill_qty * fill_price
            
            # Remove position if fully closed
            if position.quantity == 0:
                del self.account.positions[symbol]
        
        # Update buying power
        self.account.buying_power = self.account.cash
    
    def _notify_fill(self, order: Order):
        """Notify callbacks of order fill."""
        for callback in self._fill_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")
    
    async def update_price(self, symbol: str, price: float):
        """
        Update price for a symbol and check pending orders.
        
        Call this with live/simulated price updates.
        """
        self.broker.set_price(symbol, price)
        
        # Update position unrealized P&L
        if symbol in self.account.positions:
            position = self.account.positions[symbol]
            position.current_price = price
            position.unrealized_pnl = position.quantity * (price - position.avg_cost)
        
        # Check pending orders
        for order in list(self._pending_orders):
            if order.symbol == symbol:
                executed = await self._execute_order(order)
                if executed.status == OrderStatus.FILLED:
                    self._pending_orders.remove(order)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if order and order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            order.status = OrderStatus.CANCELLED
            if order in self._pending_orders:
                self._pending_orders.remove(order)
            return True
        return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    def get_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """Get all orders, optionally filtered by status."""
        if status:
            return [o for o in self._orders.values() if o.status == status]
        return list(self._orders.values())
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.account.positions.get(symbol)
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.account.positions.values())


# Example usage
async def example():
    """Example paper trading session."""
    # Create paper trader
    trader = PaperTrader(initial_capital=100000)
    
    # Register fill callback
    def on_fill(order):
        print(f"FILL: {order.side.value} {order.quantity} {order.symbol} @ ${order.filled_price:.2f}")
    
    trader.on_fill(on_fill)
    
    # Set initial prices
    await trader.update_price('AAPL', 175.00)
    await trader.update_price('GOOGL', 140.00)
    
    # Submit orders
    order1 = await trader.submit_order('AAPL', OrderSide.BUY, 100)
    order2 = await trader.submit_order('GOOGL', OrderSide.BUY, 50)
    
    print(f"\nAccount: ${trader.account.equity:.2f}")
    print(f"Positions: {[p.to_dict() for p in trader.get_positions()]}")
    
    # Simulate price change
    await trader.update_price('AAPL', 180.00)
    print(f"\nAfter AAPL rally: ${trader.account.equity:.2f}")
    
    # Sell position
    await trader.submit_order('AAPL', OrderSide.SELL, 100)
    print(f"\nAfter selling: Cash = ${trader.account.cash:.2f}")


if __name__ == '__main__':
    asyncio.run(example())
