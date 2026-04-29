from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
import uvicorn
import asyncio
import json
import logging
from typing import Dict, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from orchestration.task_orchestrator import PolyTradeOrchestrator
from config.settings import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PolyTrade v7 API",
    description="Advanced Polymarket Trading System with Hyperliquid Price Feeds",
    version="7.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ui.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize trading system
orchestrator = PolyTradeOrchestrator()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_ids: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_ids[websocket] = str(id(websocket))[:8]
        logger.info(f"Client connected: {self.connection_ids[websocket]}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        conn_id = self.connection_ids.pop(websocket, 'unknown')
        logger.info(f"Client disconnected: {conn_id}")

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)

manager = ConnectionManager()

# ============================================
# Startup and Shutdown Events
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    logger.info("=" * 50)
    logger.info("Starting PolyTrade v7 Server...")
    logger.info("=" * 50)

    try:
        await orchestrator.initialize()
        logger.info("Trading system initialized successfully")

        # Start background tasks
        asyncio.create_task(broadcast_market_data())
        asyncio.create_task(broadcast_system_health())

        logger.info("Background tasks started")
        logger.info("Server is ready to accept connections")

    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down PolyTrade v7...")
    try:
        await orchestrator.shutdown()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# ============================================
# Root and UI Routes
# ============================================

@app.get("/")
async def root():
    """Root endpoint - serves the main dashboard"""
    # Check if static UI files exist
    ui_index_path = os.path.join(os.path.dirname(__file__), "..", "out", "index.html")

    if os.path.exists(ui_index_path):
        return FileResponse(ui_index_path)

    # Fallback to API status page
    return JSONResponse({
        "name": "PolyTrade v7",
        "version": "7.0.0",
        "status": "operational",
        "endpoints": {
            "dashboard": "/",
            "api_health": "/api/health",
            "api_docs": "/api/docs",
            "api_portfolio": "/api/portfolio",
            "api_positions": "/api/positions",
            "api_signals": "/api/signals",
            "api_whale_alerts": "/api/alerts/whales",
            "api_backtest": "/api/backtest/results",
            "api_execution_stats": "/api/execution/stats",
            "api_market_snapshot": "/api/market/snapshot",
            "websocket": "ws://<host>/ws"
        },
        "system_state": orchestrator.state.value,
        "uptime": "running",
        "timestamp": datetime.now().isoformat(),
        "message": "API is running. Build the UI with 'cd ui && npm run build' to see the dashboard."
    })

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = os.path.join(os.path.dirname(__file__), "..", "out", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse({"status": "no favicon"}, status_code=404)

# ============================================
# API Routes - Health & System
# ============================================

@app.get("/api/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "system_state": orchestrator.state.value,
        "active_positions": len(orchestrator.active_positions),
        "portfolio_value": orchestrator.portfolio['total_value'],
        "ws_connections": manager.connection_count,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def system_status():
    """Detailed system status"""
    return {
        "system": {
            "state": orchestrator.state.value,
            "environment": config.environment,
            "paper_trading": config.paper_trading
        },
        "connections": {
            "websocket_clients": manager.connection_count,
            "exchange": "Hyperliquid",
            "polymarket": "Connected"
        },
        "performance": orchestrator.performance_metrics,
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# API Routes - Portfolio & Trading
# ============================================

@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio status"""
    return {
        "portfolio": orchestrator.portfolio,
        "performance": orchestrator.performance_metrics,
        "active_positions_count": len(orchestrator.active_positions),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/positions")
async def get_positions():
    """Get active positions"""
    positions = []
    for order_id, position in orchestrator.active_positions.items():
        positions.append({
            "order_id": order_id,
            "symbol": position.get('signal', {}).get('symbol', ''),
            "direction": position.get('signal', {}).get('action', 'HOLD'),
            "entry_price": position.get('entry_price', 0),
            "size": position.get('size', 0),
            "pnl": position.get('unrealized_pnl', 0),
            "timestamp": str(position.get('timestamp', datetime.now()))
        })

    return {
        "positions": positions,
        "count": len(positions),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/trade/execute")
async def execute_trade(trade_data: dict):
    """Execute a manual trade"""
    try:
        signal = {
            'action': trade_data.get('action', 'HOLD'),
            'position_size': float(trade_data.get('size', 0)),
            'entry_price': float(trade_data.get('price', 0)),
            'token_id': trade_data.get('token_id', ''),
            'symbol': trade_data.get('symbol', '')
        }

        if signal['position_size'] <= 0:
            raise HTTPException(status_code=400, detail="Invalid position size")

        if signal['action'] not in ['BUY', 'SELL']:
            raise HTTPException(status_code=400, detail="Action must be BUY or SELL")

        result = await orchestrator.executor.execute_trade(signal, [])

        return {
            "success": result.get('success', False),
            "order_id": result.get('order_id', ''),
            "filled_price": result.get('filled_price', 0),
            "execution_time_ms": result.get('execution_time_ms', 0),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/positions/close/{order_id}")
async def close_position(order_id: str):
    """Close a specific position"""
    if order_id not in orchestrator.active_positions:
        raise HTTPException(status_code=404, detail="Position not found")

    try:
        position = orchestrator.active_positions[order_id]
        result = await orchestrator.executor.close_position(order_id, position)
        return {
            "success": result.get('success', False),
            "pnl": result.get('pnl', 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to close position {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# API Routes - Signals & Intelligence
# ============================================

@app.get("/api/signals")
async def get_signals():
    """Get latest AI trading signals"""
    signals = []

    # Get market data for signal generation
    if orchestrator.data_pipeline:
        try:
            snapshot = await orchestrator.data_pipeline.get_market_snapshot()
            for symbol, data in snapshot.items():
                signals.append({
                    "symbol": symbol,
                    "exchange_price": data.exchange_price,
                    "poly_bid": data.polymarket_orderbook.best_bid,
                    "poly_ask": data.polymarket_orderbook.best_ask,
                    "spread": data.polymarket_orderbook.spread,
                    "latency_gap": data.latency_gap,
                    "volume_24h": data.volume_24h,
                    "price_change_5m": data.price_change_5m,
                    "indicators": data.indicators,
                    "timestamp": str(data.timestamp)
                })
        except Exception as e:
            logger.error(f"Error generating signals: {e}")

    return {
        "signals": signals,
        "count": len(signals),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/alerts/whales")
async def get_whale_alerts():
    """Get whale activity alerts"""
    alerts = []
    if orchestrator.market_intelligence:
        try:
            alerts = await orchestrator.market_intelligence.get_whale_alerts(limit=20)
        except Exception as e:
            logger.error(f"Error getting whale alerts: {e}")

    return {
        "alerts": alerts,
        "count": len(alerts),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/market/snapshot")
async def get_market_snapshot():
    """Get current market snapshot"""
    snapshot = {}
    if orchestrator.data_pipeline:
        try:
            raw_snapshot = await orchestrator.data_pipeline.get_market_snapshot()
            # Convert to serializable format
            for symbol, data in raw_snapshot.items():
                snapshot[symbol] = {
                    "exchange_price": data.exchange_price,
                    "poly_bid": data.polymarket_orderbook.best_bid,
                    "poly_ask": data.polymarket_orderbook.best_ask,
                    "spread": data.polymarket_orderbook.spread,
                    "latency_gap": data.latency_gap,
                    "volume_24h": data.volume_24h,
                    "price_change_1m": data.price_change_1m,
                    "price_change_5m": data.price_change_5m,
                    "volatility": data.volatility
                }
        except Exception as e:
            logger.error(f"Error getting market snapshot: {e}")

    return {
        "snapshot": snapshot,
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# API Routes - Backtesting & Analytics
# ============================================

@app.get("/api/backtest/results")
async def get_backtest_results():
    """Get latest backtest results"""
    results = {}
    if orchestrator.backtest_engine:
        try:
            results = orchestrator.backtest_engine.get_performance_summary()
        except Exception as e:
            logger.error(f"Error getting backtest results: {e}")

    return {
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/backtest/run")
async def run_backtest(backtest_config: dict):
    """Run a new backtest"""
    try:
        symbol = backtest_config.get('symbol', 'BTC')
        strategy = backtest_config.get('strategy', {})
        timeframe = backtest_config.get('timeframe', '5m')

        if orchestrator.backtest_engine:
            result = await orchestrator.backtest_engine.run_full_backtest(
                strategy, symbol, timeframe
            )
            if result:
                return {
                    "success": True,
                    "summary": orchestrator.backtest_engine.get_performance_summary(),
                    "timestamp": datetime.now().isoformat()
                }

        return {"success": False, "message": "Backtest failed"}
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# API Routes - Execution & Stats
# ============================================

@app.get("/api/execution/stats")
async def get_execution_stats():
    """Get execution statistics"""
    stats = {}
    if orchestrator.executor:
        try:
            stats = await orchestrator.executor.get_execution_stats()
        except Exception as e:
            logger.error(f"Error getting execution stats: {e}")

    return {
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# API Routes - System Control
# ============================================

@app.post("/api/system/control")
async def system_control(control_data: dict):
    """Control system state"""
    action = control_data.get('action', '')

    if action == 'start':
        orchestrator.state = type(orchestrator.state).RUNNING
        message = "System started"

    elif action == 'pause':
        orchestrator.state = type(orchestrator.state).PAUSED
        message = "System paused"

    elif action == 'emergency_stop':
        orchestrator.state = type(orchestrator.state).EMERGENCY_STOP
        if orchestrator.executor:
            await orchestrator.executor.emergency_close_all()
        message = "Emergency stop activated - all positions closed"

    elif action == 'resume':
        orchestrator.state = type(orchestrator.state).RUNNING
        message = "System resumed"

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    return {
        "status": "success",
        "action": action,
        "message": message,
        "current_state": orchestrator.state.value,
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# WebSocket Endpoint
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send welcome message
    await manager.send_personal({
        "type": "connection",
        "status": "connected",
        "message": "Connected to PolyTrade v7",
        "client_id": manager.connection_ids.get(websocket, 'unknown'),
        "timestamp": datetime.now().isoformat()
    }, websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            msg_type = data.get('type', '')

            if msg_type == 'subscribe':
                channels = data.get('channels', [])
                await manager.send_personal({
                    "type": "subscription",
                    "channels": channels,
                    "status": "subscribed",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

            elif msg_type == 'ping':
                await manager.send_personal({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

            elif msg_type == 'get_market_data':
                snapshot = {}
                if orchestrator.data_pipeline:
                    raw = await orchestrator.data_pipeline.get_market_snapshot()
                    for sym, data in raw.items():
                        snapshot[sym] = {
                            "exchange_price": data.exchange_price,
                            "poly_bid": data.polymarket_orderbook.best_bid,
                            "poly_ask": data.polymarket_orderbook.best_ask,
                            "latency_gap": data.latency_gap
                        }
                await manager.send_personal({
                    "type": "market_data",
                    "data": snapshot,
                    "timestamp": datetime.now().isoformat()
                }, websocket)

            else:
                await manager.send_personal({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# ============================================
# Background Tasks
# ============================================

async def broadcast_market_data():
    """Broadcast market data to WebSocket clients periodically"""
    logger.info("Market data broadcast started")

    while True:
        try:
            if manager.active_connections and orchestrator.data_pipeline:
                snapshot = await orchestrator.data_pipeline.get_market_snapshot()

                # Convert to serializable format
                serializable = {}
                for symbol, data in snapshot.items():
                    serializable[symbol] = {
                        "exchange_price": data.exchange_price,
                        "poly_bid": data.polymarket_orderbook.best_bid,
                        "poly_ask": data.polymarket_orderbook.best_ask,
                        "spread": data.polymarket_orderbook.spread,
                        "latency_gap": data.latency_gap,
                        "volume_24h": data.volume_24h,
                        "price_change_5m": data.price_change_5m,
                        "volatility": data.volatility
                    }

                await manager.broadcast({
                    "type": "market_update",
                    "data": serializable,
                    "timestamp": datetime.now().isoformat()
                })

            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Market data broadcast error: {e}")
            await asyncio.sleep(1)

async def broadcast_system_health():
    """Broadcast system health status periodically"""
    logger.info("System health broadcast started")

    while True:
        try:
            if manager.active_connections:
                await manager.broadcast({
                    "type": "health_update",
                    "data": {
                        "state": orchestrator.state.value,
                        "portfolio_value": orchestrator.portfolio['total_value'],
                        "active_positions": len(orchestrator.active_positions),
                        "ws_connections": manager.connection_count
                    },
                    "timestamp": datetime.now().isoformat()
                })

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Health broadcast error: {e}")
            await asyncio.sleep(1)

# ============================================
# Static Files (UI) - Must be after all routes
# ============================================

# Serve the Next.js static export
ui_build_path = os.path.join(os.path.dirname(__file__), "..", "out")
if os.path.exists(ui_build_path):
    # Mount static files for the UI
    app.mount("/", StaticFiles(directory=ui_build_path, html=True), name="ui")
    logger.info(f"UI static files mounted from: {ui_build_path}")
else:
    logger.warning(f"UI build not found at {ui_build_path}. Run 'cd ui && npm run build' to generate it.")

# ============================================
# Main Entry Point
# ============================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=config.ui.debug,
        log_level=config.log_level.lower(),
        workers=1
    )
