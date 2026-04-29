PolyTrade v-7 Configuration Management
Handles all environment variables, API keys, and system parameters
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
import yaml

load_dotenv()

@dataclass
class AIConfig:
    """AI/LLM Configuration for all brain layers"""
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = "deepseek-chat"
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_models: List[str] = field(default_factory=lambda: [
        "qwen/qwen-2.5-72b-instruct",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.3-70b-instruct"
    ])
    miroshark_enabled: bool = True
    aeon_enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.1
    context_window: int = 100000

@dataclass
class MarketDataConfig:
    """Market data pipeline configuration"""
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    update_frequency_ms: int = 50  # 50ms latency target
    symbols_monitored: List[str] = field(default_factory=lambda: [
        "btcusdt", "ethusdt", "solusdt"
    ])
    contract_durations: List[int] = field(default_factory=lambda: [5, 15])

@dataclass
class RiskConfig:
    """Risk management parameters"""
    max_position_size_pct: float = 0.05  # Max 5% per trade
    max_daily_loss_pct: float = 0.15  # Max 15% daily drawdown
    kelly_fraction: float = 0.25  # Quarter Kelly for safety
    min_edge_required: float = 0.02  # Minimum 2% edge to trade
    max_correlation: float = 0.7  # Max allowed position correlation
    kill_switch_enabled: bool = True
    circuit_breaker_threshold: int = 10  # Stop after 10 consecutive losses

@dataclass
class ExecutionConfig:
    """Trade execution parameters"""
    polymarket_private_key: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    network_id: int = 137  # Polygon
    rpc_url: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    gas_limit: int = 300000
    max_slippage_bps: int = 50  # 0.5% max slippage
    order_timeout_seconds: int = 5
    retry_attempts: int = 3

@dataclass
class DatabaseConfig:
    """Database configuration"""
    postgres_url: str = os.getenv("DATABASE_URL", "postgresql://localhost:5432/polytrade")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    timescaledb_enabled: bool = True
    retention_days: int = 90

@dataclass
class UIConfig:
    """Frontend configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

@dataclass
class SystemConfig:
    """Master configuration combining all subsystems"""
    ai: AIConfig = field(default_factory=AIConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    
    # System-wide settings
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    paper_trading: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"
    
    @classmethod
    def load_from_yaml(cls, path: str = "config.yaml"):
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)
    
    def save_to_yaml(self, path: str = "config.yaml"):
        """Save current configuration to YAML"""
        config_data = {
            "ai": self.ai.__dict__,
            "market_data": self.market_data.__dict__,
            "risk": self.risk.__dict__,
            "execution": self.execution.__dict__,
            "database": self.database.__dict__,
            "ui": self.ui.__dict__
        }
        with open(path, 'w') as f:
            yaml.dump(config_data, f)

# Global config instance
config = SystemConfig()
