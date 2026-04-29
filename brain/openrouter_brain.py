import asyncio
import json
import logging
from typing import Dict, List, Optional
import aiohttp
import numpy as np
from config.settings import config

logger = logging.getLogger(__name__)

class OpenRouterBrain:
    def __init__(self):
        self.api_key = config.ai.openrouter_api_key
        self.models = config.ai.openrouter_models
        self.base_url = "https://openrouter.ai/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self.model_weights = {
            "qwen/qwen-2.5-72b-instruct": 0.3,
            "anthropic/claude-3.5-sonnet": 0.25,
            "google/gemini-pro-1.5": 0.25,
            "meta-llama/llama-3.3-70b-instruct": 0.2
        }

    async def initialize(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info(f"OpenRouter brain initialized with {len(self.models)} models")

    async def get_consensus_signal(self, market_data: Dict) -> Dict:
        await self.initialize()
        tasks = [self._query_model(model, market_data) for model in self.models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals = []
        for model, result in zip(self.models, results):
            if isinstance(result, Exception):
                continue
            if result.get('success'):
                parsed = self._parse_model_signal(result)
                if parsed:
                    parsed['weight'] = self.model_weights.get(model, 0.1)
                    parsed['model'] = model
                    signals.append(parsed)
        return self._form_consensus(signals)

    async def _query_model(self, model: str, market_data: Dict) -> Dict:
        try:
            prompt = f"""Analyze this Polymarket opportunity:
            Symbol: {market_data.get('symbol')}
            Binance Price: ${market_data.get('binance_price')}
            Poly Bid/Ask: {market_data.get('polymarket_bid')}/{market_data.get('polymarket_ask')}
            Provide: action (BUY/SELL/HOLD), confidence (0-1), edge_percentage, reasoning. Format as JSON."""
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a quantitative trading analyst."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://polytrade-v7.app",
                "X-Title": "PolyTrade v7"
            }
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=20
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {"success": True, "model": model, "content": result['choices'][0]['message']['content']}
                return {"success": False, "error": await response.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_model_signal(self, result: Dict) -> Optional[Dict]:
        try:
            content = result['content']
            if '{' in content:
                start = content.index('{')
                end = content.rindex('}') + 1
                json_str = content[start:end]
                parsed = json.loads(json_str)
                return {
                    'action': parsed.get('action', 'HOLD'),
                    'confidence': float(parsed.get('confidence', 0)),
                    'edge': float(parsed.get('edge_percentage', parsed.get('edge', 0))),
                    'reasoning': parsed.get('reasoning', '')
                }
        except:
            pass
        return None

    def _form_consensus(self, signals: List[Dict]) -> Dict:
        if not signals:
            return {'action': 'HOLD', 'confidence': 0, 'edge': 0, 'consensus_strength': 0}
        votes = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        total_weight = sum(s.get('weight', 0.1) for s in signals)
        for s in signals:
            votes[s.get('action', 'HOLD')] += s.get('weight', 0.1)
        max_votes = max(votes.values())
        winning_action = max(votes, key=votes.get)
        consensus_strength = max_votes / total_weight if total_weight > 0 else 0
        avg_edge = np.mean([s.get('edge', 0) for s in signals])
        avg_confidence = np.mean([s.get('confidence', 0) for s in signals])
        if consensus_strength < 0.6:
            winning_action = 'HOLD'
        return {
            'action': winning_action,
            'confidence': avg_confidence,
            'edge': avg_edge,
            'consensus_strength': consensus_strength,
            'model_count': len(signals)
        }

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None
