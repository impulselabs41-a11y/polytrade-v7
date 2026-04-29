import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self):
        self.active_orders: Dict[str, Dict] = {}
        self.filled_orders: Dict[str, Dict] = {}
        self.execution_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'avg_fill_time_ms': 0
        }
        self.last_order_time = 0
        self.min_order_interval = 0.1

    async def initialize(self):
        logger.info("Trade executor initialized")

    async def execute_trade(self, signal: Dict, conditions: List[str]) -> Dict:
        await self._rate_limit()
        trade_start = time.time()
        self.execution_stats['total_orders'] += 1
        execution_time = (time.time() - trade_start) * 1000
        self.execution_stats['successful_orders'] += 1
        order_id = f"order_{int(time.time())}"
        result = {
            'success': True,
            'order_id': order_id,
            'filled_price': signal.get('entry_price', 0),
            'filled_size': signal.get('position_size', 0),
            'execution_time_ms': execution_time
        }
        self.filled_orders[order_id] = {'signal': signal, 'result': result, 'timestamp': datetime.now()}
        return result

    async def close_position(self, order_id: str, position: Dict) -> Dict:
        result = {'success': True, 'pnl': position.get('size', 0) * 0.01}
        self.filled_orders.pop(order_id, None)
        return result

    async def get_execution_stats(self) -> Dict:
        return {**self.execution_stats, 'active_orders': len(self.active_orders)}

    async def emergency_close_all(self) -> Dict:
        return {'success': True, 'closed_count': len(self.filled_orders)}

    async def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_order_time
        if time_since_last < self.min_order_interval:
            await asyncio.sleep(self.min_order_interval - time_since_last)
        self.last_order_time = time.time()

    async def cleanup(self):
        logger.info("Trade executor cleaned up")
