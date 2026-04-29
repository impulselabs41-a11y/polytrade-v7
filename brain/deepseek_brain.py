import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from dataclasses import dataclass
import numpy as np
from config.settings import config

logger = logging.getLogger(__name__)

@dataclass
class MarketContext:
    symbol: str
    binance_price: float
    polymarket_bid: float
    polymarket_ask: float
    volume_24h: float
    price_change_5m: float
    order_book_imbalance: float
    whale_activity: bool
    news_sentiment: float
    macro_factors: Dict[str, float]

@dataclass
class TradeSignal:
    action: str
    symbol: str
    contract_type: str
    edge: float
    confidence: float
    position_size: float
    entry_price: float
    target_price: float
    stop_loss: float
    reasoning: str
    risk_factors: List[str]
    timestamp: datetime

class DeepSeekBrain:
    def __init__(self):
        self.api_key = config.ai.deepseek_api_key
        self.model = config.ai.deepseek_model
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.conversation_history: List[Dict] = []
        self.max_history = 50

    async def initialize(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("DeepSeek brain initialized")

    async def analyze_market_opportunity(self, context: MarketContext) -> TradeSignal:
        await self.initialize()
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_analysis_prompt(context)
        analysis = await self._query_deepseek(system_prompt, user_prompt)
        signal = self._parse_ai_response(analysis, context)
        signal = await self._validate_signal(signal, context)
        self._update_history(analysis)
        return signal

    def _build_system_prompt(self) -> str:
        return """You are an elite quantitative trading system specializing in Polymarket.
        Rules:
        1. Only trade when edge > 2%
        2. Use Quarter Kelly for position sizing
        3. Always set stop-losses
        4. Never risk >5% on single trade
        Output as JSON with: action, edge_percentage, confidence, position_size_usdc, entry_price, target_price, stop_loss, reasoning, risk_factors"""

    def _build_analysis_prompt(self, context: MarketContext) -> str:
        return f"""CURRENT MARKET CONDITIONS:
        Symbol: {context.symbol}
        Exchange Price: ${context.binance_price}
        Polymarket Bid/Ask: ${context.polymarket_bid}/{context.polymarket_ask}
        24h Volume: ${context.volume_24h:,.0f}
        5min Change: {context.price_change_5m}%
        Order Book Imbalance: {context.order_book_imbalance}
        Whale Activity: {context.whale_activity}
        News Sentiment: {context.news_sentiment}
        
        Return analysis as JSON."""

    async def _query_deepseek(self, system_prompt: str, user_prompt: str) -> Dict:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-10:],
                {"role": "user", "content": user_prompt}
            ]
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": config.ai.temperature,
                "max_tokens": config.ai.max_tokens
            }
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "content": result['choices'][0]['message']['content'],
                        "tokens_used": result.get('usage', {}).get('total_tokens', 0)
                    }
                else:
                    return {"success": False, "error": await response.text()}
        except Exception as e:
            logger.error(f"DeepSeek query failed: {e}")
            return {"success": False, "error": str(e)}

    def _parse_ai_response(self, analysis: Dict, context: MarketContext) -> TradeSignal:
        if not analysis.get('success'):
            return TradeSignal(
                action="HOLD", symbol=context.symbol, contract_type="",
                edge=0, confidence=0, position_size=0, entry_price=0,
                target_price=0, stop_loss=0,
                reasoning=f"Analysis failed: {analysis.get('error')}",
                risk_factors=["AI_FAILURE"], timestamp=datetime.now()
            )
        try:
            content = analysis['content']
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0]
            elif '{' in content:
                start = content.index('{')
                end = content.rindex('}') + 1
                json_str = content[start:end]
            else:
                json_str = content
            parsed = json.loads(json_str)
            return TradeSignal(
                action=parsed.get('action', 'HOLD'),
                symbol=context.symbol,
                contract_type=parsed.get('contract_type', ''),
                edge=float(parsed.get('edge_percentage', 0)),
                confidence=float(parsed.get('confidence', 0)),
                position_size=float(parsed.get('position_size_usdc', 0)),
                entry_price=float(parsed.get('entry_price', 0)),
                target_price=float(parsed.get('target_price', 0)),
                stop_loss=float(parsed.get('stop_loss', 0)),
                reasoning=parsed.get('reasoning', ''),
                risk_factors=parsed.get('risk_factors', []),
                timestamp=datetime.now()
            )
        except Exception as e:
            return TradeSignal(
                action="HOLD", symbol=context.symbol, contract_type="",
                edge=0, confidence=0, position_size=0, entry_price=0,
                target_price=0, stop_loss=0, reasoning=f"Parse error: {e}",
                risk_factors=["PARSE_ERROR"], timestamp=datetime.now()
            )

    async def _validate_signal(self, signal: TradeSignal, context: MarketContext) -> TradeSignal:
        if signal.action == "HOLD":
            return signal
        if signal.edge < config.risk.min_edge_required:
            signal.action = "HOLD"
            signal.reasoning += " | Edge below minimum"
        max_position = 100000 * config.risk.max_position_size_pct
        if signal.position_size > max_position:
            signal.position_size = max_position
        if signal.confidence < 0.6:
            signal.position_size *= 0.5
        return signal

    def _update_history(self, analysis: Dict):
        if analysis.get('success'):
            self.conversation_history.append({
                "role": "assistant",
                "content": analysis['content']
            })
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

    async def calculate_kelly_position(self, win_probability: float, odds: float, bankroll: float) -> float:
        b = odds - 1
        p = win_probability
        q = 1 - p
        if b <= 0:
            return 0
        kelly_fraction = (b * p - q) / b
        kelly_fraction *= config.risk.kelly_fraction
        kelly_fraction = min(kelly_fraction, config.risk.max_position_size_pct)
        kelly_fraction = max(kelly_fraction, 0)
        return bankroll * kelly_fraction

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None
