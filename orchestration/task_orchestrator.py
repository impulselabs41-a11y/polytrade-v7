import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
from enum import Enum
import signal

from brain.deepseek_brain import DeepSeekBrain, MarketContext
from brain.openrouter_brain import OpenRouterBrain
from brain.miroshark_engine import MiroSharkEngine
from orchestration.agency_agents import AgencyDebateSystem
from data.market_data_pipeline import MarketDataPipeline
from intelligence.market_intelligence import MarketIntelligence
from backtest.backtest_engine import BacktestEngine
from execution.trade_executor import TradeExecutor
from config.settings import config

logger = logging.getLogger(__name__)

class SystemState(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"
    SHUTTING_DOWN = "shutting_down"

class PolyTradeOrchestrator:
    def __init__(self):
        self.deepseek_brain = DeepSeekBrain()
        self.openrouter_brain = OpenRouterBrain()
        self.miroshark = MiroSharkEngine()
        self.debate_system = AgencyDebateSystem()
        self.data_pipeline: Optional[MarketDataPipeline] = None
        self.market_intelligence: Optional[MarketIntelligence] = None
        self.backtest_engine: Optional[BacktestEngine] = None
        self.executor: Optional[TradeExecutor] = None
        self.state = SystemState.INITIALIZING
        self.active_positions: Dict[str, Dict] = {}
        self.portfolio = {
            'total_value': 100000.0, 'available_balance': 100000.0,
            'exposure_pct': 0.0, 'daily_pnl': 0.0, 'daily_loss_pct': 0.0,
            'consecutive_losses': 0, 'total_trades': 0, 'winning_trades': 0
        }
        self.performance_metrics = {
            'total_pnl': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown': 0.0,
            'win_rate': 0.0, 'profit_factor': 0.0
        }
        self.running = False
        self.tasks = []
        self.opportunity_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def initialize(self):
        logger.info("Initializing PolyTrade v7...")
        await self.deepseek_brain.initialize()
        await self.openrouter_brain.initialize()
        self.data_pipeline = MarketDataPipeline()
        await self.data_pipeline.initialize()
        self.market_intelligence = MarketIntelligence()
        await self.market_intelligence.initialize()
        self.backtest_engine = BacktestEngine()
        await self.backtest_engine.initialize()
        self.executor = TradeExecutor()
        await self.executor.initialize()
        self.state = SystemState.RUNNING
        logger.info("PolyTrade v7 initialized successfully")

    async def run(self):
        logger.info("Starting main loop...")
        self.running = True
        self.tasks = [
            asyncio.create_task(self._market_monitor_loop()),
            asyncio.create_task(self._opportunity_analyzer_loop()),
            asyncio.create_task(self._portfolio_monitor_loop())
        ]
        try:
            await asyncio.gather(*self.tasks)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
        finally:
            await self.shutdown()

    async def _market_monitor_loop(self):
        while self.running and self.state == SystemState.RUNNING:
            try:
                market_data = await self.data_pipeline.get_market_snapshot()
                for symbol, data in market_data.items():
                    if data.get('latency_gap', 0) > 1.0:
                        await self.opportunity_queue.put({'symbol': symbol, 'data': data, 'timestamp': datetime.now()})
                await asyncio.sleep(config.market_data.update_frequency_ms / 1000)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(1)

    async def _opportunity_analyzer_loop(self):
        while self.running:
            try:
                opportunity = await self.opportunity_queue.get()
                enriched_data = await self.market_intelligence.analyze(opportunity['data'])
                context = MarketContext(
                    symbol=opportunity['symbol'],
                    binance_price=enriched_data['binance_price'],
                    polymarket_bid=enriched_data.get('poly_bid', 0),
                    polymarket_ask=enriched_data.get('poly_ask', 0),
                    volume_24h=enriched_data.get('volume_24h', 0),
                    price_change_5m=enriched_data.get('price_change_5m', 0),
                    order_book_imbalance=enriched_data.get('order_imbalance', 0),
                    whale_activity=enriched_data.get('whale_activity', False),
                    news_sentiment=enriched_data.get('sentiment', 0),
                    macro_factors=enriched_data.get('macro_factors', {})
                )
                signal = await self.deepseek_brain.analyze_market_opportunity(context)
                if signal.action in ['BUY', 'SELL']:
                    debate = await self.debate_system.conduct_debate(enriched_data, signal.__dict__, self.portfolio)
                    if debate.final_decision in ['APPROVED_LONG', 'APPROVED_SHORT']:
                        await self.executor.execute_trade(signal.__dict__, debate.conditions)
                self.opportunity_queue.task_done()
            except Exception as e:
                logger.error(f"Analyzer error: {e}")

    async def _portfolio_monitor_loop(self):
        while self.running:
            total_exposure = sum(pos.get('size', 0) for pos in self.active_positions.values())
            self.portfolio['exposure_pct'] = total_exposure / self.portfolio['total_value']
            if self.portfolio['daily_loss_pct'] > config.risk.max_daily_loss_pct:
                self.state = SystemState.EMERGENCY_STOP
            await asyncio.sleep(10)

    async def shutdown(self):
        logger.info("Shutting down...")
        self.running = False
        self.state = SystemState.SHUTTING_DOWN
        await self.deepseek_brain.cleanup()
        await self.openrouter_brain.cleanup()
        for task in self.tasks:
            task.cancel()
        logger.info("Shutdown complete")
