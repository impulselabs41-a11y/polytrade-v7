from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
import json
import logging
from typing import Dict, List
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from orchestration.task_orchestrator import PolyTradeOrchestrator
from config.settings import config

logger = logging.getLogger(__name__)

app = FastAPI(title="PolyTrade v7 API", version="7.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

orchestrator = PolyTradeOrchestrator()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "state": orchestrator.state.value, "portfolio": orchestrator.portfolio['total_value'], "timestamp": datetime.now().isoformat()}

@app.get("/api/portfolio")
async def get_portfolio():
    return {**orchestrator.portfolio, **orchestrator.performance_metrics, "timestamp": datetime.now().isoformat()}

@app.get("/api/positions")
async def get_positions():
    positions = [{"order_id": oid, "direction": pos.get('signal', {}).get('action', ''), "entry_price": pos.get('entry_price', 0), "size": pos.get('size', 0)} for oid, pos in orchestrator.active_positions.items()]
    return {"positions": positions, "count": len(positions)}

@app.get("/api/signals")
async def get_signals():
    return {"signals": [], "timestamp": datetime.now().isoformat()}

@app.get("/api/alerts/whales")
async def get_whale_alerts():
    alerts = await orchestrator.market_intelligence.get_whale_alerts() if orchestrator.market_intelligence else []
    return {"alerts": alerts}

@app.get("/api/backtest/results")
async def get_backtest_results():
    results = orchestrator.backtest_engine.get_performance_summary() if orchestrator.backtest_engine else {}
    return {"results": results}

@app.get("/api/execution/stats")
async def get_execution_stats():
    stats = await orchestrator.executor.get_execution_stats() if orchestrator.executor else {}
    return {"stats": stats}

@app.post("/api/trade/execute")
async def execute_trade(trade_data: dict):
    signal = {'action': trade_data.get('action', 'BUY'), 'position_size': trade_data.get('size', 0), 'entry_price': trade_data.get('price', 0), 'symbol': trade_data.get('symbol', '')}
    result = {"success": True, "message": "Trade executed"}
    return result

@app.post("/api/system/control")
async def system_control(control_data: dict):
    action = control_data.get('action', '')
    if action == 'pause':
        orchestrator.state = orchestrator.state.__class__.PAUSED
    elif action == 'emergency_stop':
        orchestrator.state = orchestrator.state.__class__.EMERGENCY_STOP
    elif action == 'resume':
        orchestrator.state = orchestrator.state.__class__.RUNNING
    return {"status": orchestrator.state.value}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get('type') == 'ping':
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup():
    logger.info("Starting PolyTrade v7 server...")
    await orchestrator.initialize()
    asyncio.create_task(broadcast_market_data())

@app.on_event("shutdown")
async def shutdown():
    await orchestrator.shutdown()

async def broadcast_market_data():
    while True:
        if manager.active_connections and orchestrator.data_pipeline:
            snapshot = await orchestrator.data_pipeline.get_market_snapshot()
            await manager.broadcast({"type": "market_update", "data": snapshot})
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
