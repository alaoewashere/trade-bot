"""
agents/coordination/debate_moderator.py
=========================================
Debate Moderator Agent.

Orchestrates a 3-round structured investment committee debate.
Uses claude-opus-4-7 for high-quality synthesis.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class DebateModeratorAgent(BaseAgent):
    agent_id = "debate_moderator"
    department = "coordination"

    def __init__(self) -> None:
        super().__init__()
        self._agent_config["model"] = "claude-opus-4-7"
        self._agent_config["max_tokens"] = 8192

    def get_system_prompt(self) -> str:
        return """You are the Debate Moderator for a quantitative hedge fund investment committee.

YOUR ROLE:
You orchestrate a structured 3-round investment committee debate to stress-test
the proposed trade. You are neutral — your job is not to advocate for a direction
but to ensure the best arguments on both sides are heard, challenged, and synthesized.
The debate produces a more robust decision than any single agent's analysis.

DEBATE STRUCTURE:

ROUND 1 — OPENING POSITIONS
Each major agent states their position and supporting evidence:
- Technical Camp: Summarize the technical analysis consensus (trend, SMC, Wyckoff, etc.)
- Quantitative Camp: Summarize the statistical and probability analysis
- Macro Camp: State the macro and sentiment perspective
- Risk Camp: State the risk and portfolio concerns

Format for each camp:
"[CAMP] Position: [BULLISH/BEARISH/NEUTRAL]
Evidence: [3 strongest supporting points]
Key concern: [biggest risk to this position]"

ROUND 2 — CHALLENGE AND REBUTTAL
The strongest BULL presents their full case.
The strongest BEAR presents their full counter-case.
Each side must:
- Directly address the other's strongest argument
- Acknowledge any legitimate points in the opposing view
- Explain why their evidence is more reliable/relevant
- Identify what would change their mind

Format:
"[BULL/BEAR ADVOCATE] REBUTTAL:
Addressing [opposing argument]: [counter-argument]
But I acknowledge: [valid opposing point]
My strongest evidence remains: [key point]
I would change my view if: [specific condition]"

ROUND 3 — NEUTRAL SYNTHESIS
After hearing both sides, you as moderator synthesize:
- Where is there genuine consensus (even across bull/bear)?
- What is the quality of evidence on each side?
- What are the genuine uncertainties that neither side can resolve?
- What is the base case? What is the bear/bull case?
- What probability does each case deserve?

Synthesis format:
"MODERATOR SYNTHESIS:
Points of consensus: [...]
Bull case quality: [1-10] — [summary]
Bear case quality: [1-10] — [summary]
Key uncertainty: [main unresolved question]
Base case: [direction and reasoning]
Probability assigned: Bull X% | Bear Y% | Neutral Z%
Final recommendation: [LONG/SHORT/NO_TRADE] with [HIGH/MEDIUM/LOW] conviction"

MODERATOR PRINCIPLES:
1. Never allow one camp to dominate without challenge
2. Always require evidence, not assertion ("I think" is not evidence)
3. Identify logical fallacies: "We always do well in Q4" is not a signal
4. Time-box each speaker — brevity and precision over volume
5. The debate must be honest — do not artificially balance weak arguments
6. If all camps agree: note this is a high-confidence signal (rare and valuable)
7. If camps are deeply divided: note this is a low-conviction situation

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: Final synthesis direction ("bullish", "bearish", or "neutral")
- confidence: Derived from synthesis probability
- reasoning: FULL DEBATE TRANSCRIPT — all 3 rounds in detail (rich reasoning field)
- supporting_evidence: Strongest bull arguments that survived challenge
- contradicting_evidence: Strongest bear arguments that survived challenge
- key_levels: Key price levels agreed upon by both camps (if any)
- metadata: {"round1_summary": "...", "round2_rebuttal_winner": "bull/bear/draw", "synthesis_bull_pct": x, "synthesis_bear_pct": x, "debate_quality": "high/medium/low"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        if len(analysis_reports) < 3:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning="Insufficient agent reports for a meaningful debate. Need at least 3 agents.",
                supporting_evidence=[],
                contradicting_evidence=["Too few agents have reported"],
                timestamp=self._now(),
            )

        # Organize reports by department
        departments = {}
        for aid, report in analysis_reports.items():
            dept = report.metadata.get("department", "unknown") if report.metadata else "unknown"
            if dept == "unknown":
                # Infer from agent_id
                if aid in ["macro_economist", "news_analyst", "sentiment_analyst", "regulation_analyst"]:
                    dept = "market_intelligence"
                elif aid in ["trend_analyst", "price_action", "smc_expert", "wyckoff_analyst",
                             "elliott_wave", "volume_profile", "market_structure"]:
                    dept = "technical"
                elif aid in ["quant_researcher", "probability_analyst", "ml_researcher",
                             "backtesting_expert", "hf_pattern_detector"]:
                    dept = "quantitative"
                elif aid in ["cro_agent", "portfolio_manager"]:
                    dept = "risk"
                else:
                    dept = "other"

            if dept not in departments:
                departments[dept] = []
            departments[dept].append((aid, report))

        # Build debate context
        bullish_agents = [(aid, r) for aid, r in analysis_reports.items() if r.signal == "bullish"]
        bearish_agents = [(aid, r) for aid, r in analysis_reports.items() if r.signal == "bearish"]
        neutral_agents = [(aid, r) for aid, r in analysis_reports.items() if r.signal == "neutral"]

        # Find strongest bull and bear (by confidence)
        strongest_bull = max(bullish_agents, key=lambda x: x[1].confidence)[0] if bullish_agents else None
        strongest_bear = max(bearish_agents, key=lambda x: x[1].confidence)[0] if bearish_agents else None

        def format_camp(agents_list, name):
            if not agents_list:
                return f"\n[{name} CAMP]\nNo agents — camp is empty\n"
            lines = [f"\n[{name} CAMP]"]
            for aid, r in agents_list[:5]:  # Limit to 5 per camp
                lines.append(
                    f"  Agent: {aid} | Conf: {r.confidence:.2f}\n"
                    f"  Key evidence: {r.supporting_evidence[:2] if r.supporting_evidence else ['No evidence']}\n"
                    f"  Concern: {r.contradicting_evidence[0] if r.contradicting_evidence else 'None stated'}\n"
                    f"  Reasoning (excerpt): {r.reasoning[:200]}"
                )
            return "\n".join(lines)

        bull_text = format_camp(bullish_agents, "BULL")
        bear_text = format_camp(bearish_agents, "BEAR")
        neutral_text = format_camp(neutral_agents, "NEUTRAL")

        # Key levels from reports
        all_key_levels = {}
        for aid, r in analysis_reports.items():
            for k, v in r.key_levels.items():
                all_key_levels[f"{aid}_{k}"] = v

        key_levels_text = "\n".join(f"  {k}: {v}" for k, v in list(all_key_levels.items())[:20])
        market_summary = self._format_market_data(market_data)

        user_message = f"""INVESTMENT COMMITTEE DEBATE
Symbol: {symbol}
Timestamp: {self._now().isoformat()}
Total Agents Reporting: {len(analysis_reports)}

=== SIGNAL TALLY ===
Bullish: {len(bullish_agents)} agents
Bearish: {len(bearish_agents)} agents
Neutral: {len(neutral_agents)} agents
Strongest Bull: {strongest_bull if strongest_bull else "none"}
Strongest Bear: {strongest_bear if strongest_bear else "none"}

{bull_text}

{bear_text}

{neutral_text}

=== KEY PRICE LEVELS ACROSS AGENTS ===
{key_levels_text if key_levels_text else "  None reported"}

=== MARKET DATA ===
{market_summary}

=== TASK ===
Moderate the 3-round investment committee debate for {symbol}:

ROUND 1: Have each camp (Technical, Quantitative, Macro, Risk) state their opening position
with their 3 strongest evidence points and their key concern.

ROUND 2: Have the strongest bull ({strongest_bull or 'representative bull'}) and strongest bear
({strongest_bear or 'representative bear'}) engage in direct rebuttal. Each must address the
other's best argument and acknowledge any valid opposing points.

ROUND 3: As moderator, synthesize the debate. Assign probability to each outcome.
State the final recommendation with conviction level.

Return the complete 3-round debate as your AgentReport reasoning. Be thorough — this is the
investment committee's formal record.
"""

        try:
            result = self._call_claude(self.get_system_prompt(), user_message, AgentReport)
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal=result.signal,
                confidence=result.confidence,
                reasoning=result.reasoning,
                supporting_evidence=result.supporting_evidence,
                contradicting_evidence=result.contradicting_evidence,
                key_levels=result.key_levels,
                timestamp=self._now(),
                metadata={
                    **result.metadata,
                    "bull_count": len(bullish_agents),
                    "bear_count": len(bearish_agents),
                    "neutral_count": len(neutral_agents),
                    "strongest_bull": strongest_bull,
                    "strongest_bear": strongest_bear,
                },
            )
        except Exception as exc:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning=f"Debate moderation failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Debate error"],
                timestamp=self._now(),
            )
