import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AIConfig:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = "deepseek-chat"
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_models: List[str] = field(default_factory=lambda: [
        "qwen/qwen-2.5-72b-instruct",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.3-70b-instruct"
    ])
    max_tokens: int = 4096
    temperature: float = 0.1

@dataclass
class MarketDataConfig:
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    update_frequency_ms: int = 50
    symbols_monitored: List[str] = field(default_factory=lambda: ["btcusdt", "ethusdt", "solusdt"])

@dataclass
class RiskConfig:
    max_position_size_pct: float = 0.05
    max_daily_loss_pct: float = 0.15
    kelly_fraction: float = 0.25
    min_edge_required: float = 0.02
    circuit_breaker_threshold: int = 10

@dataclass
class ExecutionConfig:
    polymarket_private_key: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    network_id: int = 137
    rpc_url: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    max_slippage_bps: int = 50
    order_timeout_seconds: int = 5
    retry_attempts: int = 3

@dataclass
class DatabaseConfig:
    postgres_url: str = os.getenv("DATABASE_URL", "postgresql://localhost:5432/polytrade")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

@dataclass
class UIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

@dataclass
class SystemConfig:
    ai: AIConfig = field(default_factory=AIConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    paper_trading: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"

config = SystemConfig()
