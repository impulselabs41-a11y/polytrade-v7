import asyncio
import logging
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class AgentRole(Enum):
    BULL = "bull"
    BEAR = "bear"
    RISK_MANAGER = "risk_manager"

@dataclass
class AgentArgument:
    role: AgentRole
    position: str
    conviction: float
    evidence: List[str]
    counter_arguments: List[str]
    position_size_recommendation: float
    risk_concerns: List[str]

@dataclass
class DebateOutcome:
    final_decision: str
    consensus_level: float
    position_size: float
    conditions: List[str]
    veto_triggers: List[str]
    debate_log: List[Dict]
    timestamp: datetime

class AgencyDebateSystem:
    def __init__(self):
        self.debate_history: List[DebateOutcome] = []
        self.veto_power = True

    async def conduct_debate(self, market_data: Dict, ai_signal: Dict, portfolio_state: Dict) -> DebateOutcome:
        debate_log = []
        arguments = {}
        for role in [AgentRole.BULL, AgentRole.BEAR, AgentRole.RISK_MANAGER]:
            argument = await self._get_agent_argument(role, market_data, ai_signal, portfolio_state)
            arguments[role] = argument
            debate_log.append({'phase': 'initial', 'role': role.value, 'position': argument.position})
        risk_assessment = await self._risk_manager_review(arguments, market_data, portfolio_state)
        outcome = self._form_consensus(arguments, risk_assessment, debate_log)
        self.debate_history.append(outcome)
        return outcome

    async def _get_agent_argument(self, role: AgentRole, market_data: Dict, ai_signal: Dict, portfolio: Dict) -> AgentArgument:
        if role == AgentRole.BULL:
            position = "LONG" if ai_signal.get('edge', 0) > 0.02 else "NEUTRAL"
            conviction = min(ai_signal.get('confidence', 0) * 1.2, 1.0)
            evidence = [f"Edge: {ai_signal.get('edge', 0)*100:.2f}%"]
        elif role == AgentRole.BEAR:
            position = "SHORT" if ai_signal.get('edge', 0) < -0.02 else "NEUTRAL"
            conviction = min(abs(ai_signal.get('edge', 0)) * 0.8, 0.9)
            evidence = ["Mean reversion likely", "Market correlation risk"]
        else:
            position = "NEUTRAL"
            conviction = 0.5
            evidence = [f"Portfolio exposure: {portfolio.get('exposure_pct', 0)}%"]
        return AgentArgument(role=role, position=position, conviction=conviction, evidence=evidence, counter_arguments=[], position_size_recommendation=ai_signal.get('position_size', 0) * 0.5, risk_concerns=[])

    async def _risk_manager_review(self, arguments: Dict, market_data: Dict, portfolio: Dict) -> Dict:
        risk_score = 0.3
        veto_triggers = []
        if portfolio.get('daily_loss_pct', 0) > 0.15:
            veto_triggers.append("DAILY_LOSS_LIMIT")
        if portfolio.get('consecutive_losses', 0) > 10:
            veto_triggers.append("CONSECUTIVE_LOSSES")
        return {'risk_score': risk_score, 'veto': len(veto_triggers) > 0, 'veto_triggers': veto_triggers, 'required_conditions': ["Position size within limits", "Stop-loss set"]}

    def _form_consensus(self, arguments: Dict, risk_assessment: Dict, debate_log: List) -> DebateOutcome:
        positions = [arg.position for arg in arguments.values()]
        long_count = positions.count("LONG")
        if risk_assessment.get('veto'):
            final_decision = "REJECTED"
            consensus_level = 0.0
        elif long_count >= 2:
            final_decision = "APPROVED_LONG"
            consensus_level = long_count / len(positions)
        else:
            final_decision = "HOLD"
            consensus_level = 0.5
        return DebateOutcome(final_decision=final_decision, consensus_level=consensus_level, position_size=1000, conditions=risk_assessment.get('required_conditions', []), veto_triggers=risk_assessment.get('veto_triggers', []), debate_log=debate_log, timestamp=datetime.now())
