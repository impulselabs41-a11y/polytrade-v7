import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque
import numpy as np
import websockets
import aiohttp
from dataclasses import dataclass, field
import pandas as pd
from config.settings import config

logger = logging.getLogger(__name__)

@dataclass
class OrderBook:
    bids: List[List[float]]
    asks: List[List[float]]
    timestamp: datetime
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    mid_price: float = 0.0
    imbalance: float = 0.0

    def __post_init__(self):
        self.best_bid = self.bids[0][0] if self.bids else 0
        self.best_ask = self.asks[0][0] if self.asks else 0
        self.spread = self.best_ask - self.best_bid
        self.mid_price = (self.best_bid + self.best_ask) / 2 if self.best_bid and self.best_ask else 0
        total_bids = sum(bid[1] for bid in self.bids[:10])
        total_asks = sum(ask[1] for ask in self.asks[:10])
        total = total_bids + total_asks
        self.imbalance = (total_bids - total_asks) / total if total > 0 else 0

@dataclass
class MarketSnapshot:
    symbol: str
    binance_price: float
    polymarket_orderbook: OrderBook
    latency_gap: float
    volume_24h: float
    price_change_1m: float
    price_change_5m: float
    volatility: float
    timestamp: datetime
    indicators: Dict[str, float] = field(default_factory=dict)

class MarketDataPipeline:
    def __init__(self):
        self.binance_ws_url = config.market_data.binance_ws_url
        self.polymarket_api = config.market_data.polymarket_api_url
        self.polymarket_gamma = config.market_data.polymarket_gamma_url
        self.binance_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.binance_prices: Dict[str, deque] = {}
        self.polymarket_books: Dict[str, OrderBook] = {}
        self.price_history: Dict[str, deque] = {}

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        for symbol in config.market_data.symbols_monitored:
            self.binance_prices[symbol] = deque(maxlen=10000)
            self.price_history[symbol] = deque(maxlen=5000)
        await self._connect_binance_ws()
        logger.info("Market data pipeline initialized")

    async def _connect_binance_ws(self):
        streams = [f"{symbol}@trade" for symbol in config.market_data.symbols_monitored]
        stream_url = f"{self.binance_ws_url}/{'/'.join(streams)}"
        try:
            self.binance_ws = await websockets.connect(stream_url)
            asyncio.create_task(self._binance_listener())
        except Exception as e:
            logger.error(f"Binance WS connection failed: {e}")

    async def _binance_listener(self):
        try:
            async for message in self.binance_ws:
                msg = json.loads(message)
                if msg.get('e') == 'trade':
                    symbol = msg['s'].lower()
                    price = float(msg['p'])
                    self.binance_prices[symbol].append({'price': price, 'timestamp': msg['T']})
        except Exception as e:
            logger.error(f"Binance listener error: {e}")

    async def get_market_snapshot(self) -> Dict[str, MarketSnapshot]:
        snapshots = {}
        for symbol in config.market_data.symbols_monitored:
            if symbol in self.binance_prices and len(self.binance_prices[symbol]) > 0:
                price_data = self.binance_prices[symbol][-1]
                snapshots[symbol] = MarketSnapshot(
                    symbol=symbol,
                    binance_price=price_data['price'],
                    polymarket_orderbook=OrderBook(bids=[], asks=[], timestamp=datetime.now()),
                    latency_gap=2.0,
                    volume_24h=1000000,
                    price_change_1m=0.1,
                    price_change_5m=0.5,
                    volatility=0.02,
                    timestamp=datetime.now()
                )
        return snapshots

    async def get_current_price(self, symbol: str) -> float:
        if symbol in self.binance_prices and self.binance_prices[symbol]:
            return self.binance_prices[symbol][-1]['price']
        return 0.0

    async def cleanup(self):
        if self.binance_ws:
            await self.binance_ws.close()
        if self.session:
            await self.session.close()
