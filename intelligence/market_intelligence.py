import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
import numpy as np

from data.market_data_pipeline import MarketDataPipeline
from data.external_data import ExternalDataFeed

logger = logging.getLogger(__name__)

class MarketIntelligence:
    def __init__(self):
        self.data_pipeline: Optional[MarketDataPipeline] = None
        self.external_data = ExternalDataFeed()
        self.whale_alerts: List[Dict] = []
        self.signal_history: Dict[str, List] = defaultdict(list)

    async def initialize(self):
        await self.external_data.initialize()
        logger.info("Market intelligence initialized")

    async def analyze(self, market_data: Dict) -> Dict:
        symbol = market_data.get('symbol', '')
        tasks = [
            self._analyze_order_flow(market_data),
            self._detect_whale_activity(symbol),
            self._analyze_sentiment(symbol)
        ]
        results = await asyncio.gather(*tasks)
        enriched = {
            **market_data,
            'order_flow_analysis': results[0],
            'whale_activity': results[1],
            'sentiment_analysis': results[2],
            'poly_bid': market_data.get('polymarket_orderbook', {}).get('best_bid', 0),
            'poly_ask': market_data.get('polymarket_orderbook', {}).get('best_ask', 0),
            'order_imbalance': 0.1,
            'volume_24h': market_data.get('volume_24h', 50000),
            'price_change_5m': market_data.get('price_change_5m', 0.5),
            'sentiment': 0.2,
            'macro_factors': {'cpi': 3.2, 'fed_rate': 5.25}
        }
        consensus = self._generate_consensus_signal(enriched)
        enriched.update(consensus)
        return enriched

    async def _analyze_order_flow(self, data: Dict) -> Dict:
        return {'signal': 'neutral', 'strength': 0.5}

    async def _detect_whale_activity(self, symbol: str) -> Dict:
        return {'active': False, 'direction': 'neutral'}

    async def _analyze_sentiment(self, symbol: str) -> Dict:
        return {'combined_score': 0.2, 'classification': 'neutral'}

    def _generate_consensus_signal(self, data: Dict) -> Dict:
        return {'consensus_signal': 'HOLD', 'consensus_strength': 0.3, 'conviction': 0.5}

    async def get_whale_alerts(self, limit: int = 10) -> List[Dict]:
        return self.whale_alerts[:limit]

    async def cleanup(self):
        await self.external_data.cleanup()
