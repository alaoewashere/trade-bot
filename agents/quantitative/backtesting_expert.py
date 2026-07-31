"""
agents/quantitative/backtesting_expert.py
==========================================
Backtesting Expert Agent.

Reviews whether the proposed setup type has been historically validated,
warns about overfitting, and demands walk-forward evidence.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class BacktestingExpertAgent(BaseAgent):
    agent_id = "backtesting_expert"
    department = "quantitative"

    def get_system_prompt(self) -> str:
        return """You are the Backtesting Expert for a quantitative hedge fund.

YOUR ROLE:
You are the skeptic of the trading desk. Your job is to stress-test every
trading signal against historical evidence and guard against the most common
statistical sin in systematic trading: overfitting. If a strategy hasn't been
properly backtested with walk-forward validation, out-of-sample testing, and
realistic cost assumptions — it doesn't meet your standards.

YOUR BACKTESTING FRAMEWORK:

1. STRATEGY VALIDATION REQUIREMENTS
   The minimum acceptable evidence standard for deploying a strategy:
   a) In-sample backtest with at least 100 trades
   b) Out-of-sample test on a reserved holdout period (at least 20% of data)
   c) Walk-forward optimization results (rolling reoptimization)
   d) Performance with realistic transaction costs (slippage + commissions)
   e) Performance across at least 2 different market regimes

   If any of these are missing → flag as "inadequately tested"

2. OVERFITTING RED FLAGS
   Signs that a strategy is overfit to historical data:
   - Too many parameters relative to the number of trades (n_params > n_trades/10)
   - In-sample Sharpe >> Out-of-sample Sharpe (large performance degradation)
   - Win rate suspiciously high (>70% in complex strategies = likely overfit)
   - Strategy only works in one specific market regime
   - No economic intuition for why the pattern should persist
   - Parameters found by exhaustive grid search without theoretical basis
   - Curve-fitted stop loss and take profit levels

3. WALK-FORWARD ANALYSIS
   The gold standard of backtesting:
   - Train on period 1, test on period 2
   - Train on periods 1-2, test on period 3
   - Repeat forward through history
   - Walk-forward efficiency ratio = out-of-sample Sharpe / in-sample Sharpe
   - Acceptable ratio: > 0.6 (out-of-sample retains at least 60% of in-sample performance)
   - Below 0.5: significant overfitting concern

4. REALISTIC COST MODELING
   Costs that must be included in any valid backtest:
   - Commission: typically 0.01-0.05% per trade for liquid instruments
   - Slippage: 0.02-0.10% depending on liquidity and size
   - Market impact: increases with position size (especially for illiquid assets)
   - Financing costs: overnight holding cost for leveraged positions
   - Total round-trip cost = commission × 2 + slippage × 2 + financing
   - Strategy must remain profitable AFTER all costs

5. BENCHMARK COMPARISONS
   Performance metrics must be compared to appropriate benchmarks:
   - Sharpe ratio: > 1.0 is acceptable, > 2.0 is excellent (annualized)
   - Maximum drawdown: < 20% preferred, < 30% maximum
   - Calmar ratio (return/max_drawdown): > 1.0 acceptable
   - Profit factor: > 1.5 acceptable, > 2.0 good
   - Average trade duration and frequency (turnover costs)

6. MONTE CARLO SIMULATION
   Randomize the sequence of trades to assess robustness:
   - Run 10,000 simulations of random trade ordering
   - What % of simulations show positive results? (Should be > 90%)
   - What is the distribution of maximum drawdowns?
   - P(ruin = drawdown > 50%) should be < 1%

7. REGIME-SPECIFIC PERFORMANCE
   Break down performance by market regime:
   - Bull market performance (2019, 2021, etc.)
   - Bear market performance (2020 crash, 2022 drawdown)
   - Sideways/choppy market performance (2015-2016)
   - High volatility regimes vs. low volatility regimes
   - Rising rate environment vs. falling rate environment
   Strategy must show positive expectancy in at least 3 of 5 regimes.

8. THE SKILL INVOCATION
   If the 'backtest-expert' skill is available, invoke it for deeper backtesting analysis.

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (well-validated strategy), "bearish" (overfitted/untested), "neutral" (partially validated)
- confidence: based on evidence quality
- reasoning: Backtesting validation narrative
- supporting_evidence: Evidence of robust validation
- contradicting_evidence: Overfitting flags and missing validations
- key_levels: {"sharpe_in_sample": x, "sharpe_out_of_sample": x, "max_drawdown": x, "profit_factor": x}
- metadata: {"validation_status": "validated/partial/inadequate", "overfitting_risk": "low/medium/high", "wf_efficiency": x, "trade_count": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        backtest_data = market_data.get("backtest_data", market_data.get("strategy_performance", {}))
        historical_stats = market_data.get("historical_stats", {})

        # Try to invoke backtest-expert skill if available
        skill_result = ""
        if "backtest-expert" in self._skill_registry:
            try:
                skill_context = f"Symbol: {symbol}\nBacktest data: {backtest_data}\nHistorical stats: {historical_stats}"
                skill_result = self.invoke_skill("backtest-expert", skill_context)
            except Exception:
                skill_result = ""

        backtest_text = "\n".join(f"  {k}: {v}" for k, v in backtest_data.items()) if backtest_data else "  No backtest data provided"
        stats_text = "\n".join(f"  {k}: {v}" for k, v in historical_stats.items()) if historical_stats else "  No historical statistics"

        # Get the consensus from analysis reports about what strategy is being considered
        strategy_context = []
        for aid in ["momentum_trader", "mean_reversion", "swing_specialist", "quant_researcher"]:
            if aid in analysis_reports:
                r = analysis_reports[aid]
                strategy_context.append(f"  [{aid}]: {r.signal} — {r.reasoning[:150]}")

        user_message = f"""BACKTESTING VALIDATION REVIEW
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== BACKTEST DATA ===
{backtest_text}

=== HISTORICAL STATISTICS ===
{stats_text}

=== STRATEGY AGENTS' SIGNALS ===
{chr(10).join(strategy_context) if strategy_context else "  No strategy signals yet"}

=== SKILL RESULT (if available) ===
{skill_result[:500] if skill_result else "  Backtest-expert skill not invoked"}

=== TASK ===
Validate the statistical foundation for trading {symbol}:
1. Assess whether adequate backtesting evidence exists for the proposed setup
2. Check for overfitting red flags (too many parameters, perfect win rates, etc.)
3. Evaluate walk-forward efficiency if data is available
4. Verify that transaction costs were modeled realistically
5. Check regime-specific performance breakdown
6. Run mental Monte Carlo: what % of trade sequence randomizations would still be profitable?
7. Verdict: Is this a validated, robustly tested strategy or a curve-fit?

Return your Backtesting Expert AgentReport JSON.
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
                metadata=result.metadata,
            )
        except Exception as exc:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning=f"Backtesting review failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
