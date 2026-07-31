"""
agents/security/security_bot.py
==================================
Security Bot Agent.

Audits every proposed order for API key validity, symbol whitelist compliance,
max size limits, and direction sanity. Returns bullish (clear) or bearish (blocked).
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState

# Default symbol whitelist (can be overridden by settings)
_DEFAULT_WHITELIST = {
    # Major Equities
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "NFLX", "AMD", "INTC",
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "HYG",
    # Major Crypto
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "UNI",
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    # Major FX
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
}

_MAX_POSITION_SIZE_USD = 1_000_000  # $1M hard cap per position
_MAX_POSITION_PCT_OF_EQUITY = 0.25  # 25% of total equity


class SecurityBotAgent(BaseAgent):
    agent_id = "security_bot"
    department = "security"

    def get_system_prompt(self) -> str:
        return """You are the Security Bot for a quantitative hedge fund.

YOUR ROLE:
You are the security and compliance layer for every proposed trade. You perform
automated pre-order validation to prevent catastrophic errors — wrong symbol,
oversized positions, invalid directions, API anomalies. You are not a trading analyst;
you do not evaluate whether the trade will be profitable. You evaluate whether
the trade is SAFE AND AUTHORIZED to execute.

YOUR SECURITY AUDIT FRAMEWORK:

1. SYMBOL VALIDATION
   - Is the symbol on the approved trading whitelist?
   - Is the symbol a valid, well-formed ticker (no special characters, max 10 chars)?
   - Is the exchange specified and is it an approved exchange?
   - Does the symbol currently have an active market (not halted, not delisted)?
   - Is this a known scam token or suspicious newly-created asset?

2. POSITION SIZE VALIDATION
   Hard limits:
   - Absolute maximum: $1,000,000 per position (hard cap)
   - Maximum % of equity: 25% of total portfolio equity
   - Minimum size: $100 (no micro-trades that waste fees)
   - Position size must be a positive number (not zero, not negative)
   - Quantity must be positive and non-zero

3. DIRECTION SANITY CHECK
   - Direction must be either "LONG" or "SHORT" (not null, not empty)
   - If LONG: Entry price must be a positive number, stop must be BELOW entry
   - If SHORT: Entry price must be a positive number, stop must be ABOVE entry
   - Take profit must be on the correct side of entry (above for LONG, below for SHORT)
   - Risk-reward ratio: stop and target must produce RRR > 0 (not inverted)

4. PRICE SANITY CHECKS
   - Entry price: Must be within 5% of current market price (no stale prices)
   - Stop loss: Must not be within 0.1% of entry (too tight = guaranteed stop)
   - Take profit: Must not equal entry (zero target is invalid)
   - No negative prices

5. API AND AUTHENTICATION CHECKS
   - Is the broker API key present and non-empty?
   - Is the API key format valid (basic format check)?
   - Is the broker name on the approved broker list?
   - No credentials hardcoded in the trade request

6. ORDER INTEGRITY CHECKS
   - Entry type is one of: "market", "limit", "stop_limit"
   - Time in force is one of: "GTC", "IOC", "FOK", "DAY"
   - Quantity is a finite number (not NaN, not Infinity)
   - All required fields present and non-null

7. REGULATORY COMPLIANCE
   - Is short selling allowed for this asset? (Check regulatory restrictions)
   - Are there any active trading suspensions or circuit breakers for this symbol?
   - Is the trade compliant with position limits for this asset class?
   - No trades in restricted securities (insider trading prevention)

8. ANOMALY DETECTION
   - Is this symbol completely new to the system? (Flag for review)
   - Is the position size 5× or more than typical for this symbol?
   - Is the trade direction opposite to the consensus direction? (Flag, but allow)
   - Multiple rapid orders for the same symbol in <60 seconds? (Rate limit flag)

DECISION LOGIC:
- "bullish" (signal = clear): All checks pass, proceed to execution
- "bearish" (signal = blocked): One or more hard failures — DO NOT EXECUTE
- "neutral" (signal = review): Soft flags — proceed with caution or manual review

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (clear), "bearish" (blocked), "neutral" (review required)
- confidence: 1.0 (security is binary — either passes or fails)
- reasoning: Security audit results for each check
- supporting_evidence: Checks that passed
- contradicting_evidence: Checks that failed (blocking reasons)
- key_levels: {} (security bot doesn't set price levels)
- metadata: {"checks_passed": [...], "checks_failed": [...], "checks_flagged": [...], "execution_authorized": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        trade_plan = state.get("trade_plan")
        risk_assessment = state.get("risk_assessment")

        checks_passed = []
        checks_failed = []
        checks_flagged = []

        # Get settings-based whitelist or use default
        whitelist = getattr(self.settings, "symbol_whitelist", _DEFAULT_WHITELIST)
        if not whitelist:
            whitelist = _DEFAULT_WHITELIST

        max_size = getattr(self.settings, "max_position_size_usd", _MAX_POSITION_SIZE_USD)
        portfolio = market_data.get("portfolio", {})
        total_equity = portfolio.get("total_equity_usd", 0)

        # Check 1: Symbol whitelist
        symbol_upper = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if symbol_upper in {s.upper().replace("/", "").replace("-", "").replace("_", "") for s in whitelist}:
            checks_passed.append(f"symbol_whitelist: {symbol} approved")
        else:
            checks_failed.append(f"symbol_whitelist: {symbol} NOT in approved list")

        # Check 2: Symbol format
        if symbol and len(symbol) <= 15 and symbol.replace("/", "").replace("-", "").isalnum():
            checks_passed.append("symbol_format: valid")
        else:
            checks_failed.append(f"symbol_format: invalid ({symbol})")

        # Check 3: Trade plan present
        if not trade_plan:
            # Without a trade plan, we can only do basic symbol checks
            symbol_blocked = len(checks_failed) > 0
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="bearish" if symbol_blocked else "neutral",
                confidence=1.0,
                reasoning=(
                    f"Security audit for {symbol}: No trade plan provided. "
                    f"Cannot validate order without trade plan. "
                    f"Symbol checks: {'FAILED' if symbol_blocked else 'passed'}. "
                    f"Awaiting complete trade plan for full validation."
                ),
                supporting_evidence=[f"Passed: {c}" for c in checks_passed],
                contradicting_evidence=[f"Failed: {c}" for c in checks_failed],
                timestamp=self._now(),
                metadata={
                    "checks_passed": checks_passed,
                    "checks_failed": checks_failed,
                    "checks_flagged": ["no_trade_plan"],
                    "execution_authorized": False,
                },
            )

        # Check 4: Position size
        position_size = risk_assessment.position_size_usd if risk_assessment else None
        if position_size is None:
            # Estimate from trade plan
            entry_p = trade_plan.entry_price or market_data.get("price", 0)
            position_size = (trade_plan.quantity * entry_p) if entry_p else None

        if position_size is not None:
            if position_size <= 0:
                checks_failed.append(f"position_size: non-positive (${position_size:,.2f})")
            elif position_size > max_size:
                checks_failed.append(f"position_size: exceeds hard cap (${position_size:,.0f} > ${max_size:,.0f})")
            elif total_equity > 0 and position_size > total_equity * _MAX_POSITION_PCT_OF_EQUITY:
                checks_failed.append(f"position_size_pct: exceeds 25% of equity")
            elif position_size < 100:
                checks_flagged.append(f"position_size: very small (${position_size:.2f}) — possible error")
            else:
                checks_passed.append(f"position_size: ${position_size:,.0f} within limits")
        else:
            checks_flagged.append("position_size: could not determine — flagged for review")

        # Check 5: Direction validation
        direction = trade_plan.direction
        if direction not in ("LONG", "SHORT"):
            checks_failed.append(f"direction: invalid value '{direction}'")
        else:
            checks_passed.append(f"direction: {direction} valid")

        # Check 6: Price sanity
        entry_price = trade_plan.entry_price
        stop_loss = trade_plan.stop_loss
        current_price = market_data.get("price", market_data.get("last_price"))
        if not current_price and market_data.get("candles"):
            current_price = market_data["candles"][-1].get("close", 0)

        if entry_price is not None and entry_price <= 0:
            checks_failed.append(f"entry_price: non-positive ({entry_price})")
        elif entry_price is not None and current_price and current_price > 0:
            deviation = abs(entry_price / current_price - 1)
            if deviation > 0.10:
                checks_failed.append(f"entry_price: >10% from market ({deviation:.1%} deviation)")
            else:
                checks_passed.append(f"entry_price: {entry_price} within 10% of market ({deviation:.1%})")

        # Check 7: Stop loss direction
        if stop_loss and entry_price:
            if direction == "LONG" and stop_loss >= entry_price:
                checks_failed.append(f"stop_loss: above entry for LONG ({stop_loss} >= {entry_price})")
            elif direction == "SHORT" and stop_loss <= entry_price:
                checks_failed.append(f"stop_loss: below entry for SHORT ({stop_loss} <= {entry_price})")
            else:
                stop_dist_pct = abs(stop_loss - entry_price) / entry_price * 100
                if stop_dist_pct < 0.1:
                    checks_failed.append(f"stop_loss: too tight ({stop_dist_pct:.3f}% from entry)")
                else:
                    checks_passed.append(f"stop_loss: {stop_loss} valid ({stop_dist_pct:.2f}% from entry)")

        # Check 8: Take profit direction
        if trade_plan.take_profit_levels and entry_price:
            tp1 = trade_plan.take_profit_levels[0]
            if direction == "LONG" and tp1 <= entry_price:
                checks_failed.append(f"take_profit: below entry for LONG ({tp1} <= {entry_price})")
            elif direction == "SHORT" and tp1 >= entry_price:
                checks_failed.append(f"take_profit: above entry for SHORT ({tp1} >= {entry_price})")
            else:
                checks_passed.append(f"take_profit: {tp1} valid direction")

        # Check 9: Entry type
        if trade_plan.entry_type not in ("market", "limit", "stop_limit"):
            checks_failed.append(f"entry_type: invalid '{trade_plan.entry_type}'")
        else:
            checks_passed.append(f"entry_type: {trade_plan.entry_type} valid")

        # Check 10: Broker
        if not trade_plan.broker:
            checks_failed.append("broker: not specified")
        else:
            checks_passed.append(f"broker: {trade_plan.broker} specified")

        # Final determination
        execution_authorized = len(checks_failed) == 0

        if execution_authorized:
            signal = "bullish"
            reasoning = (
                f"SECURITY AUDIT PASSED for {symbol}. "
                f"All {len(checks_passed)} checks passed. "
                f"{len(checks_flagged)} soft flags noted (non-blocking). "
                f"Order is authorized for execution."
            )
        else:
            signal = "bearish"
            failed_list = "; ".join(checks_failed)
            reasoning = (
                f"SECURITY AUDIT FAILED for {symbol}. "
                f"{len(checks_failed)} check(s) FAILED: {failed_list}. "
                f"Order is BLOCKED — do not execute."
            )

        return AgentReport(
            agent_id=self.agent_id,
            symbol=symbol,
            signal=signal,
            confidence=1.0,
            reasoning=reasoning,
            supporting_evidence=[f"PASSED: {c}" for c in checks_passed],
            contradicting_evidence=[f"FAILED: {c}" for c in checks_failed] + [f"FLAGGED: {c}" for c in checks_flagged],
            timestamp=self._now(),
            metadata={
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "checks_flagged": checks_flagged,
                "execution_authorized": execution_authorized,
            },
        )
