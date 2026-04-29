# PolyTrade v7 - Advanced Polymarket Trading System

Production-grade prediction market trading bot with 6-layer AI architecture.

## Architecture
- **Layer 1:** AI Brain (DeepSeek, OpenRouter, MiroShark)
- **Layer 2:** Orchestration (Multi-Agent Debate System)
- **Layer 3:** Data Pipeline (Real-time Market Data)
- **Layer 4:** Market Intelligence (Whale Tracking, Sentiment)
- **Layer 5:** Backtesting & Simulation
- **Layer 6:** Trade Execution (CLOB Integration)

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/polytrade-v7.git
cd polytrade-v7

# Set up environment variables
cp .env.example .env
# Edit .env with your actual API keys

# Run with Docker
docker-compose up -d

# Or run locally
pip install -r requirements.txt
cd ui && npm install && npm run build
uvicorn ui.backend.server:app --reload
