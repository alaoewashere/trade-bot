"""
agents/monitoring/performance_analyst.py
==========================================
Performance Analyst Agent.

Calculates win rate, Sharpe ratio, profit factor, max drawdown, and other
key performance metrics from trade history.
"""

from __future__ import annotations

import math

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class PerformanceAnalystAgent(BaseAgent):
    agent_id = "performance_analyst"
    department = "monitoring"

    def get_system_prompt(self) -> str:
        return """You are the Performance Analyst for a quantitative hedge fund.

YOUR ROLE:
You are the accountability mechanism of the trading operation. You calculate,
interpret, and contextualize all trading performance metrics. You don't just
report numbers — you diagnose what they mean, identify deteriorating performance
early, and recommend corrective action. You are the objective voice that separates
skill from luck.

YOUR PERFORMANCE ANALYTICS FRAMEWORK:

1. CORE PERFORMANCE METRICS
   Win Rate = (Number of profitable trades) / (Total trades) × 100
   - > 60%: High win rate (verify expected value still positive)
   - 45-60%: Normal range for most strategies
   - < 45%: Low win rate (requires high RRR to be profitable)

   Average Win / Average Loss:
   - Win/Loss ratio = Avg Win size / Avg Loss size
   - Minimum acceptable: 1.0 (break even at 50% win rate)
   - With 40% win rate, need Win/Loss > 1.5 to be profitable

   Profit Factor = Gross Profit / Gross Loss
   - < 1.0: System is losing money
   - 1.0-1.5: Marginally profitable (high costs could eliminate edge)
   - 1.5-2.0: Good
   - > 2.0: Excellent

2. RISK-ADJUSTED RETURNS
   Sharpe Ratio = (Portfolio Return - Risk-free Rate) / Standard Deviation of Returns
   - Annualized using: Sharpe = (Daily Sharpe) × sqrt(252) for stocks, × sqrt(365) for crypto
   - < 0: Underperforming risk-free rate
   - 0-1: Acceptable but not great
   - 1-2: Good — institutional quality
   - 2-3: Very good — excellent systematic strategy
   - > 3: Exceptional — rare and may indicate overfitting

   Sortino Ratio = (Portfolio Return - Risk-free Rate) / Downside Deviation
   - Better than Sharpe because only penalizes downside volatility
   - Target > 2.0

   Calmar Ratio = Annualized Return / Maximum Drawdown
   - > 1.0: Acceptable
   - > 2.0: Good
   - > 3.0: Excellent

3. DRAWDOWN ANALYSIS
   Maximum Drawdown (MDD):
   - MDD = (Peak Value - Trough Value) / Peak Value × 100
   - < 10%: Very conservative, typical for market-neutral strategies
   - 10-20%: Acceptable for directional strategies
   - 20-30%: Elevated — review risk management
   - > 30%: Dangerous — fundamental risk management failure

   Average Drawdown: Typical drawdown, not just the worst
   Recovery Time: How long to recover from the maximum drawdown?
   Drawdown Duration: Time spent in drawdown > 10% of equity

4. CONSISTENCY METRICS
   Monthly Win Rate: % of months with positive returns
   - > 70%: Very consistent
   - 50-70%: Normal
   - < 50%: Inconsistent — strategy may be failing

   Return Distribution:
   - Skewness: Positive skew preferred (small losses, occasional big wins)
   - Kurtosis: Fat-tailed returns (either direction) = more risk than normal distribution implies

5. STRATEGY-SPECIFIC PERFORMANCE BREAKDOWN
   Break down performance by:
   - By agent/strategy: Which signals have been most accurate?
   - By market regime: How does performance differ in bull vs. bear markets?
   - By symbol/sector: Are there consistent winners/losers?
   - By time of day: Are morning or afternoon trades more profitable?
   - By hold duration: Short-term vs. medium-term vs. long-term

6. PERFORMANCE DEGRADATION DETECTION
   Warning signals:
   - Win rate declining over rolling 20-trade window
   - Average win size shrinking while average loss stable
   - Profit factor declining below 1.3
   - Maximum drawdown exceeding 15% and still recovering
   - Sharpe ratio declining below 1.0

7. BENCHMARK COMPARISON
   Compare performance to relevant benchmarks:
   - SPY (for equity strategies): Is the strategy alpha-generating?
   - BTC (for crypto strategies): Outperforming simple buy-and-hold?
   - 60/40 portfolio: Classic balanced benchmark
   - Information Ratio: Active return divided by tracking error

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (performance good/improving), "bearish" (performance degrading), "neutral" (stable/mixed)
- confidence: based on sample size and data quality
- reasoning: Performance analysis narrative with specific metrics
- supporting_evidence: Strong performance metrics
- contradicting_evidence: Performance concerns or degradation signals
- key_levels: {"win_rate": x, "sharpe": x, "profit_factor": x, "max_drawdown": x, "calmar": x}
- metadata: {"total_trades": x, "avg_win_usd": x, "avg_loss_usd": x, "current_drawdown_pct": x, "monthly_win_rate": x, "performance_trend": "improving/stable/degrading"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        performance_data = market_data.get("performance_data", {})
        trade_history = market_data.get("trade_history", market_data.get("recent_trades", []))

        if not performance_data and not trade_history:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No performance data available. This agent requires trade history to function.",
                supporting_evidence=[],
                contradicting_evidence=["No performance_data or trade_history provided"],
                timestamp=self._now(),
            )

        # Extract pre-computed metrics
        win_rate = performance_data.get("win_rate")
        profit_factor = performance_data.get("profit_factor")
        sharpe = performance_data.get("sharpe_ratio")
        sortino = performance_data.get("sortino_ratio")
        max_dd = performance_data.get("max_drawdown_pct")
        current_dd = performance_data.get("current_drawdown_pct", 0)
        total_trades = performance_data.get("total_trades", len(trade_history))
        avg_win = performance_data.get("avg_win_usd")
        avg_loss = performance_data.get("avg_loss_usd")
        calmar = performance_data.get("calmar_ratio")
        monthly_win_rate = performance_data.get("monthly_win_rate")

        # Compute basic metrics from raw trades if not pre-computed
        computed_from_raw = False
        if not performance_data and trade_history:
            wins = [t for t in trade_history if t.get("pnl", 0) > 0]
            losses = [t for t in trade_history if t.get("pnl", 0) <= 0]
            if trade_history:
                win_rate = len(wins) / len(trade_history) * 100
                avg_win = sum(t.get("pnl", 0) for t in wins) / max(len(wins), 1)
                avg_loss = abs(sum(t.get("pnl", 0) for t in losses) / max(len(losses), 1))
                gross_profit = sum(t.get("pnl", 0) for t in wins)
                gross_loss = abs(sum(t.get("pnl", 0) for t in losses))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
                computed_from_raw = True

        perf_text = "\n".join(f"  {k}: {v}" for k, v in performance_data.items()) if performance_data else ""

        # Format recent trades
        trade_lines = []
        for i, t in enumerate(trade_history[-20:]):
            if isinstance(t, dict):
                pnl = t.get("pnl", 0)
                trade_lines.append(
                    f"  [{i+1}] {t.get('symbol','?')} {t.get('side','?')} | "
                    f"entry={t.get('entry',0):.4f} exit={t.get('exit',0):.4f} | "
                    f"P&L=${pnl:,.2f} | date={t.get('date','?')}"
                )

        trades_text = "\n".join(trade_lines) if trade_lines else "  No individual trade data"

        user_message = f"""PERFORMANCE ANALYSIS REQUEST
Symbol Context: {symbol}
Timestamp: {self._now().isoformat()}

=== PRE-COMPUTED METRICS ===
  Win Rate: {f'{win_rate:.1f}%' if win_rate is not None else "N/A"}
  Profit Factor: {f'{profit_factor:.2f}' if profit_factor is not None else "N/A"}
  Sharpe Ratio (annualized): {f'{sharpe:.2f}' if sharpe is not None else "N/A"}
  Sortino Ratio: {f'{sortino:.2f}' if sortino is not None else "N/A"}
  Max Drawdown: {f'{max_dd:.2f}%' if max_dd is not None else "N/A"}
  Current Drawdown: {f'{current_dd:.2f}%' if current_dd is not None else "N/A"}
  Calmar Ratio: {f'{calmar:.2f}' if calmar is not None else "N/A"}
  Total Trades: {total_trades}
  Avg Win: {f'${avg_win:,.2f}' if avg_win is not None else "N/A"}
  Avg Loss: {f'${avg_loss:,.2f}' if avg_loss is not None else "N/A"}
  Monthly Win Rate: {f'{monthly_win_rate:.1f}%' if monthly_win_rate is not None else "N/A"}
  Computed from raw trades: {computed_from_raw}

{perf_text}

=== RECENT TRADES (last 20) ===
{trades_text}

=== TASK ===
Analyze trading performance:
1. Evaluate all core metrics against professional benchmarks
2. Assess trend in performance (improving, stable, or degrading)?
3. Identify which aspects of performance are strongest/weakest
4. Detect early warning signs of strategy deterioration
5. Break down performance by market regime if data allows
6. Compare to relevant benchmarks
7. Provide specific recommendations to improve performance

Return your Performance Analyst AgentReport JSON.
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
                reasoning=f"Performance analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
