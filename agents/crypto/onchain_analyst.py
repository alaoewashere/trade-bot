"""
agents/crypto/onchain_analyst.py
==================================
On-Chain Analyst Agent.

Reads on-chain data from market_data: exchange inflows/outflows, whale
activity, MVRV ratio, stablecoin supply, and miner activity.
Only active for crypto symbols.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState

# Known crypto symbols to check relevance
CRYPTO_KEYWORDS = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
                   "LINK", "UNI", "ATOM", "LTC", "BCH", "SHIB", "TRX", "NEAR", "FTM", "ALGO",
                   "USDT", "USDC", "DAI", "CRYPTO", "COIN", "PERP", "DEFI"}


class OnChainAnalystAgent(BaseAgent):
    agent_id = "onchain_analyst"
    department = "crypto"

    def get_system_prompt(self) -> str:
        return """You are the On-Chain Analyst for a quantitative hedge fund.

YOUR ROLE:
You analyze blockchain data to gain insight into the fundamental supply/demand
dynamics of cryptocurrency assets that are invisible to traditional technical and
fundamental analysts. On-chain data represents the actual behavior of market
participants — what they are doing, not just what price is telling you.

YOUR ON-CHAIN ANALYTICAL FRAMEWORK:

1. EXCHANGE INFLOWS & OUTFLOWS (Critical Signal)
   - Exchange Inflow: Crypto moving TO exchanges (selling intent)
     → High inflows = bearish (coins being deposited to sell)
     → Inflow spike before price drop = smart money distribution
   - Exchange Outflow: Crypto moving FROM exchanges (HODLing intent)
     → High outflows = bullish (coins being withdrawn to cold storage)
     → Sustained outflows = supply squeeze → price appreciation likely
   - Net Exchange Flow = Inflows - Outflows
     → Consistently negative (more outflows) = bullish accumulation
     → Consistently positive (more inflows) = bearish distribution

2. WHALE WALLET ACTIVITY
   Definition: Wallets holding >1000 BTC (or equivalent in other assets)
   - Whale accumulation (increasing holdings): Bullish → whales buying = price support
   - Whale distribution (decreasing holdings): Bearish → whales selling into strength
   - Whale-to-exchange transfers: Early warning of large sell pressure
   - New whale wallets appearing: Fresh institutional capital entering
   - Whale concentration ratio: If few whales hold too much → centralization risk

3. MVRV RATIO (Market Value to Realized Value)
   Formula: MVRV = Market Cap / Realized Cap
   Where Realized Cap = Sum of (coins × price at last movement)

   Interpretation:
   - MVRV > 3.0: Extreme overvaluation, most holders profitable → sell pressure likely
   - MVRV 2.0–3.0: Elevated, caution — approaching historical top zones
   - MVRV 1.0–2.0: Fair value range — neutral to mildly bullish
   - MVRV 0.8–1.0: Near fair value, approaching historical bottom accumulation zones
   - MVRV < 0.8: Extreme undervaluation → historically high-conviction buy zone
     (most holders underwater = capitulation complete)

4. STABLECOIN SUPPLY & FLOWS
   Stablecoins are "dry powder" — potential buying power sitting on the sidelines.
   - Rising stablecoin supply on exchanges: More buying power accumulating → bullish
   - Declining stablecoin supply: Capital being deployed → bullish (if into crypto)
     OR capital exiting to fiat → bearish (if leaving crypto entirely)
   - Stablecoin dominance: If USDT/USDC % of crypto market cap rising → risk-off
   - Minting of new stablecoins: Fresh capital entering the ecosystem → bullish

5. MINER ACTIVITY (Bitcoin-specific)
   - Miner outflows to exchanges: Miners selling production → selling pressure
   - Miner accumulation: Miners holding, not selling → bullish (confidence in price)
   - Miner capitulation: Hash rate drops + miner selling = classic capitulation bottom signal
   - Post-halving behavior: After halving, miners reduce sell pressure → supply shock → bullish
   - Hash ribbons: When short-term hash rate crosses above long-term → buy signal

6. HOLDER BEHAVIOR METRICS
   - Long-Term Holder (LTH) Supply: Holders with coins unmoved >155 days
     → LTH supply increasing = accumulation, strong hands holding
     → LTH supply decreasing = distribution (long-term holders taking profits)
   - Short-Term Holder (STH) SOPR: Indicates if recent buyers are selling at profit or loss
     → STH SOPR < 1.0: Recent buyers selling at a loss = capitulation
     → STH SOPR > 1.0: Selling at profit = profit-taking (moderate bearish pressure)
   - HODL Waves: Visualizes age distribution of coin supply

7. NETWORK HEALTH
   - Active addresses: Rising = growing user activity → bullish fundamental
   - Transaction count: Proxy for network demand
   - Fee revenue: High fees = congested network = high demand → bullish
   - New addresses: Proxy for new user adoption

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (on-chain supports upside), "bearish" (distribution signals), "neutral" (mixed/insufficient data)
- confidence: based on on-chain data quality
- reasoning: On-chain narrative covering the most significant metrics
- supporting_evidence: On-chain data points supporting the signal
- contradicting_evidence: On-chain warning signals
- key_levels: {"mvrv": x, "exchange_net_flow_24h": x, "realized_price": x}
- metadata: {"mvrv_signal": "undervalued/fair/overvalued", "whale_trend": "accumulating/distributing/neutral", "exchange_flow_bias": "inflow/outflow/balanced", "stablecoin_supply_change": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        # Check if this is a crypto asset
        is_crypto = any(kw in symbol.upper() for kw in CRYPTO_KEYWORDS)
        onchain_data = market_data.get("onchain_data", market_data.get("on_chain", {}))

        if not is_crypto and not onchain_data:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning=f"{symbol} does not appear to be a crypto asset. On-chain analysis not applicable.",
                supporting_evidence=[],
                contradicting_evidence=["Non-crypto symbol — on-chain analysis skipped"],
                timestamp=self._now(),
                metadata={"skipped": True, "reason": "non_crypto_symbol"},
            )

        if not onchain_data:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No on-chain data available for analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No onchain_data provided"],
                timestamp=self._now(),
            )

        # Parse on-chain metrics
        mvrv = onchain_data.get("mvrv", onchain_data.get("mvrv_ratio"))
        exchange_inflow = onchain_data.get("exchange_inflow_24h")
        exchange_outflow = onchain_data.get("exchange_outflow_24h")
        whale_accumulation = onchain_data.get("whale_accumulation")
        stablecoin_supply_change = onchain_data.get("stablecoin_supply_change_7d")
        miner_outflow = onchain_data.get("miner_outflow_24h")
        lth_supply = onchain_data.get("lth_supply_change_7d")
        active_addresses = onchain_data.get("active_addresses_24h")
        realized_price = onchain_data.get("realized_price")

        net_flow = None
        if exchange_inflow is not None and exchange_outflow is not None:
            net_flow = exchange_inflow - exchange_outflow

        onchain_text = "\n".join(f"  {k}: {v}" for k, v in onchain_data.items())

        user_message = f"""ON-CHAIN ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== ON-CHAIN METRICS ===
  MVRV Ratio: {mvrv if mvrv is not None else "N/A"}
  Realized Price: {realized_price if realized_price else "N/A"}
  Exchange Inflow (24h): {exchange_inflow if exchange_inflow is not None else "N/A"}
  Exchange Outflow (24h): {exchange_outflow if exchange_outflow is not None else "N/A"}
  Net Exchange Flow (24h): {net_flow if net_flow is not None else "N/A"}
  Whale Accumulation: {whale_accumulation if whale_accumulation is not None else "N/A"}
  Miner Outflow (24h): {miner_outflow if miner_outflow is not None else "N/A"}
  LTH Supply Change (7d): {lth_supply if lth_supply is not None else "N/A"}
  Stablecoin Supply Change (7d): {stablecoin_supply_change if stablecoin_supply_change is not None else "N/A"}
  Active Addresses (24h): {active_addresses if active_addresses is not None else "N/A"}

=== ALL ON-CHAIN DATA ===
{onchain_text}

=== TASK ===
Perform comprehensive on-chain analysis for {symbol}:
1. Interpret the MVRV ratio — is the asset fundamentally over/undervalued?
2. Analyze exchange flows — are coins being deposited (sell) or withdrawn (HODL)?
3. Assess whale behavior — accumulating or distributing?
4. Evaluate miner activity (if BTC) — selling or holding?
5. Check stablecoin supply for pending buying power
6. Review LTH behavior — are long-term holders exiting?
7. Synthesize: What is the on-chain narrative for {symbol}?

Return your On-Chain Analyst AgentReport JSON.
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
                reasoning=f"On-chain analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
