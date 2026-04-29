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
    exchange_price: float  # renamed from binance_price - now Hyperliquid
    polymarket_orderbook: OrderBook
    latency_gap: float
    volume_24h: float
    price_change_1m: float
    price_change_5m: float
    volatility: float
    timestamp: datetime
    indicators: Dict[str, float] = field(default_factory=dict)

class MarketDataPipeline:
    """
    Real-time market data pipeline
    Uses Hyperliquid WebSocket for CEX prices instead of Binance
    """

    def __init__(self):
        # Hyperliquid endpoints
        self.hyperliquid_ws_url = config.market_data.hyperliquid_ws_url
        self.hyperliquid_rest_url = config.market_data.hyperliquid_rest_url

        # Polymarket endpoints
        self.polymarket_api = config.market_data.polymarket_api_url
        self.polymarket_gamma = config.market_data.polymarket_gamma_url

        # WebSocket connection
        self.hyperliquid_ws: Optional[websockets.WebSocketClientProtocol] = None

        # REST session
        self.session: Optional[aiohttp.ClientSession] = None

        # Price storage - stores mid prices from Hyperliquid
        self.hl_mid_prices: Dict[str, float] = {
            "BTC": 0.0,
            "ETH": 0.0
        }

        # Price history for indicators
        self.price_history: Dict[str, deque] = {
            "BTC": deque(maxlen=5000),
            "ETH": deque(maxlen=5000)
        }

        # Polymarket order books
        self.polymarket_books: Dict[str, OrderBook] = {}

        # Metrics
        self.update_count = 0
        self.error_count = 0
        self._running = True

    async def initialize(self):
        """Initialize data pipeline"""
        self.session = aiohttp.ClientSession()

        # Start Hyperliquid WebSocket connection
        asyncio.create_task(self._connect_hyperliquid_ws())

        logger.info("Market data pipeline initialized (Hyperliquid + Polymarket)")

    async def _connect_hyperliquid_ws(self):
        """Connect to Hyperliquid WebSocket for real-time mid prices"""
        while self._running:
            try:
                logger.info(f"Connecting to Hyperliquid WebSocket: {self.hyperliquid_ws_url}")
                async with websockets.connect(
                    self.hyperliquid_ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self.hyperliquid_ws = ws

                    # Subscribe to allMids - gives you mid price for EVERY coin
                    sub_msg = json.dumps({"type": "allMids"})
                    await ws.send(sub_msg)
                    logger.info("Subscribed to Hyperliquid 'allMids' stream")

                    # Listen for messages
                    async for message in ws:
                        await self._process_hyperliquid_message(message)

            except websockets.ConnectionClosed:
                logger.warning("Hyperliquid WebSocket disconnected. Reconnecting in 3 seconds...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Hyperliquid WebSocket error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _process_hyperliquid_message(self, raw_message: str):
        """Process incoming Hyperliquid WebSocket message"""
        try:
            data = json.loads(raw_message)

            # Handle 'allMids' channel
            if data.get("channel") == "allMids":
                mids = data.get("data", {}).get("mids", {})

                # Update BTC and ETH prices
                for symbol in config.market_data.symbols_monitored:
                    if symbol in mids:
                        price = float(mids[symbol])
                        self.hl_mid_prices[symbol] = price

                        # Store in history for indicators
                        self.price_history[symbol].append({
                            'price': price,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        })

                self.update_count += 1

        except json.JSONDecodeError:
            logger.debug(f"Failed to parse Hyperliquid message: {raw_message[:200]}")
        except Exception as e:
            logger.error(f"Error processing Hyperliquid message: {e}")
            self.error_count += 1

    async def get_market_snapshot(self) -> Dict[str, MarketSnapshot]:
        """Get current market snapshot for all monitored symbols"""
        snapshots = {}

        for symbol in config.market_data.symbols_monitored:
            try:
                # Get Hyperliquid mid price (from WebSocket cache - extremely fast)
                exchange_price = self.hl_mid_prices.get(symbol, 0.0)

                # Get Polymarket order book
                poly_book = await self._get_polymarket_orderbook(symbol)
                if poly_book is None:
                    poly_book = OrderBook(
                        bids=[], asks=[],
                        timestamp=datetime.now()
                    )

                # Calculate latency gap (rough estimate)
                latency_gap = self._estimate_latency_gap(poly_book.timestamp)

                # Get volume from Polymarket
                volume_24h = await self._get_polymarket_volume(symbol)

                # Calculate price changes from history
                changes = self._calculate_price_changes(symbol)

                # Calculate volatility
                volatility = self._calculate_volatility(symbol)

                # Calculate technical indicators
                indicators = self._calculate_indicators(symbol)

                snapshots[symbol] = MarketSnapshot(
                    symbol=symbol,
                    exchange_price=exchange_price,
                    polymarket_orderbook=poly_book,
                    latency_gap=latency_gap,
                    volume_24h=volume_24h,
                    price_change_1m=changes.get('1m', 0),
                    price_change_5m=changes.get('5m', 0),
                    volatility=volatility,
                    timestamp=datetime.now(),
                    indicators=indicators
                )

            except Exception as e:
                logger.error(f"Error getting snapshot for {symbol}: {e}")

        return snapshots

    async def _get_polymarket_orderbook(self, symbol: str) -> Optional[OrderBook]:
        """Get Polymarket order book for a symbol"""
        try:
            # Try to find active markets for this symbol
            async with self.session.get(
                f"{self.polymarket_gamma}/markets",
                params={"tag": "crypto", "active": "true", "limit": 20}
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                markets = data if isinstance(data, list) else data.get('markets', [])

                # Find a market matching our symbol
                for market in markets:
                    question = market.get('question', '').lower()
                    if symbol.lower() in question:
                        token_id = market.get('clobTokenIds', '[]')
                        if isinstance(token_id, str):
                            token_id = json.loads(token_id)
                        if isinstance(token_id, list) and len(token_id) > 0:
                            token_id = token_id[0]
                            return await self._fetch_orderbook(token_id)

                return None

        except Exception as e:
            logger.error(f"Failed to get Polymarket orderbook for {symbol}: {e}")
            return None

    async def _fetch_orderbook(self, token_id: str) -> Optional[OrderBook]:
        """Fetch order book for a specific token"""
        try:
            async with self.session.get(
                f"{self.polymarket_api}/book",
                params={"token_id": token_id}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    bids = data.get('bids', [])
                    asks = data.get('asks', [])

                    # Parse bids/asks into [[price, size], ...]
                    parsed_bids = [[float(b.get('price', 0)), float(b.get('size', 0))] for b in bids]
                    parsed_asks = [[float(a.get('price', 0)), float(a.get('size', 0))] for a in asks]

                    return OrderBook(
                        bids=parsed_bids,
                        asks=parsed_asks,
                        timestamp=datetime.now()
                    )
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {token_id}: {e}")

        return None

    async def _get_polymarket_volume(self, symbol: str) -> float:
        """Get 24h volume from Polymarket"""
        try:
            async with self.session.get(
                f"{self.polymarket_gamma}/markets",
                params={"tag": "crypto", "active": "true"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = data if isinstance(data, list) else data.get('markets', [])
                    total_volume = 0
                    for market in markets:
                        question = market.get('question', '').lower()
                        if symbol.lower() in question:
                            total_volume += float(market.get('volume24hr', 0))
                    return total_volume
        except Exception:
            pass
        return 0.0

    def _estimate_latency_gap(self, poly_timestamp: datetime) -> float:
        """Estimate latency gap between exchange and Polymarket"""
        # This is a rough estimate - Hyperliquid WebSocket is extremely fast (~10-50ms)
        # Polymarket REST is slower (~200-500ms)
        now = datetime.now()
        gap_seconds = (now - poly_timestamp).total_seconds()
        return max(gap_seconds, 0.01)  # Minimum 10ms

    def _calculate_price_changes(self, symbol: str) -> Dict[str, float]:
        """Calculate price changes over different timeframes"""
        changes = {'1m': 0.0, '5m': 0.0, '15m': 0.0}

        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            return changes

        history = list(self.price_history[symbol])
        if not history:
            return changes

        current_price = history[-1]['price']
        current_ts = history[-1]['timestamp']

        # 1 minute change
        one_min_ago = current_ts - 60000
        prices_1m = [p for p in history if p['timestamp'] >= one_min_ago]
        if prices_1m and prices_1m[0]['price'] != 0:
            changes['1m'] = ((current_price - prices_1m[0]['price']) / prices_1m[0]['price']) * 100

        # 5 minute change
        five_min_ago = current_ts - 300000
        prices_5m = [p for p in history if p['timestamp'] >= five_min_ago]
        if prices_5m and prices_5m[0]['price'] != 0:
            changes['5m'] = ((current_price - prices_5m[0]['price']) / prices_5m[0]['price']) * 100

        # 15 minute change
        fifteen_min_ago = current_ts - 900000
        prices_15m = [p for p in history if p['timestamp'] >= fifteen_min_ago]
        if prices_15m and prices_15m[0]['price'] != 0:
            changes['15m'] = ((current_price - prices_15m[0]['price']) / prices_15m[0]['price']) * 100

        return changes

    def _calculate_volatility(self, symbol: str) -> float:
        """Calculate price volatility from history"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            return 0.0

        prices = [p['price'] for p in list(self.price_history[symbol])[-100:]]
        if len(prices) < 2:
            return 0.0

        returns = np.diff(np.log(prices))
        volatility = np.std(returns) * np.sqrt(365 * 24 * 60)  # Annualized
        return float(volatility)

    def _calculate_indicators(self, symbol: str) -> Dict[str, float]:
        """Calculate technical indicators"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
            return {}

        prices = np.array([p['price'] for p in list(self.price_history[symbol])[-100:]])

        indicators = {}

        # RSI (14-period)
        indicators['rsi'] = self._calculate_rsi(prices)

        # Moving averages
        if len(prices) >= 10:
            indicators['sma_10'] = float(np.mean(prices[-10:]))
        if len(prices) >= 20:
            indicators['sma_20'] = float(np.mean(prices[-20:]))

        return indicators

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices[-period - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    async def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        # Normalize symbol to match Hyperliquid format (BTC, ETH)
        clean_symbol = symbol.upper().replace("USDT", "").replace("USD", "").strip()
        return self.hl_mid_prices.get(clean_symbol, 0.0)

    async def get_order_book_snapshot(self, symbol: str) -> Optional[OrderBook]:
        """Get current order book for a symbol"""
        return await self._get_polymarket_orderbook(symbol)

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = '1h',
        limit: int = 100
    ) -> pd.DataFrame:
        """Get historical price data from Hyperliquid REST API"""
        try:
            clean_symbol = symbol.upper().replace("USDT", "").replace("USD", "").strip()

            # Map timeframe to Hyperliquid candle interval
            timeframe_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '1h': '1h',
                '4h': '4h',
                '1d': '1d'
            }
            interval = timeframe_map.get(timeframe, '1h')

            # Hyperliquid info endpoint for metadata
            async with self.session.post(
                f"{self.hyperliquid_rest_url}/info",
                json={"type": "meta"}
            ) as response:
                if response.status == 200:
                    meta = await response.json()
                    # Find the coin's szDecimals
                    universe = meta.get('universe', [])
                    coin_info = next((u for u in universe if u.get('name') == clean_symbol), None)

                    if coin_info:
                        # Now get candle data
                        async with self.session.post(
                            f"{self.hyperliquid_rest_url}/info",
                            json={
                                "type": "candleSnapshot",
                                "req": {
                                    "coin": clean_symbol,
                                    "interval": interval,
                                    "startTime": int(
                                        (datetime.now().timestamp() - 3600 * limit) * 1000
                                    ),
                                    "endTime": int(datetime.now().timestamp() * 1000)
                                }
                            }
                        ) as candle_response:
                            if candle_response.status == 200:
                                candles = await candle_response.json()

                                if candles:
                                    df = pd.DataFrame(candles)
                                    df['t'] = pd.to_datetime(df['t'], unit='ms')
                                    df = df.rename(columns={
                                        't': 'timestamp',
                                        'o': 'open',
                                        'h': 'high',
                                        'l': 'low',
                                        'c': 'close',
                                        'v': 'volume'
                                    })
                                    df.set_index('timestamp', inplace=True)
                                    return df

            # Fallback to empty DataFrame
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return pd.DataFrame()

    async def cleanup(self):
        """Cleanup resources"""
        self._running = False
        if self.hyperliquid_ws:
            await self.hyperliquid_ws.close()
        if self.session:
            await self.session.close()
        logger.info("Market data pipeline cleaned up")
