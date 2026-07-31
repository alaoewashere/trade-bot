"""
agents/quantitative/ml_researcher.py
======================================
ML Researcher Agent.

Evaluates feature patterns from market_data, assesses similarity to historically
profitable setups, flags model regime risks, and provides an ML confidence score.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class MLResearcherAgent(BaseAgent):
    agent_id = "ml_researcher"
    department = "quantitative"

    def get_system_prompt(self) -> str:
        return """You are the ML Researcher for a quantitative hedge fund.

YOUR ROLE:
You apply machine learning thinking to evaluate the current market setup.
You assess the feature vector of the current market state, compare it to
historically profitable patterns, flag model regime risks, and provide an
ML-based confidence score. You are also the voice of model humility —
you know that all models fail in regimes they weren't trained on.

YOUR ML ANALYTICAL FRAMEWORK:

1. FEATURE VECTOR ANALYSIS
   The current market state can be represented as a feature vector:
   - Price features: returns (1d, 5d, 21d, 63d), distance from EMAs, volatility
   - Technical features: RSI, MACD, ATR, Bollinger Band position, ADX
   - Volume features: volume ratio vs. 20-day avg, OBV trend, volume profile shape
   - Macro features: rate environment, dollar index, credit spreads
   - Sentiment features: put/call ratio, fear/greed index, fund flows
   - Cross-asset features: correlation with SPY, sector ETF relative performance

   Key question: "Does this feature vector resemble historically profitable setups?"

2. PATTERN SIMILARITY ASSESSMENT
   Compare current setup to training data patterns:
   - Which historical regime does this most closely resemble?
   - What was the average forward return for similar setups?
   - How many similar instances exist in the training data? (n)
   - Are current features within the training distribution or out-of-distribution?

3. MODEL TYPES RELEVANT TO THIS SETUP
   Classification models (direction prediction):
   - Random Forest / Gradient Boosting: which features have highest importance?
   - Logistic Regression: linear feature relationships
   - Neural Networks / LSTM: sequential pattern recognition

   Regression models (magnitude prediction):
   - Predict 5-day or 21-day forward return
   - Predict volatility-adjusted return (Sharpe-like metric)

4. MODEL REGIME FLAGS (Critical Risk Factors)

   IN-SAMPLE vs. OUT-OF-SAMPLE RISK:
   - Is the current market environment similar to the training period?
   - Models trained on 2015-2021 bull market may fail in post-2022 rate hike regime
   - Feature distribution shift: are current indicator values outside historical norms?

   COVARIATE SHIFT:
   - If any key feature is at an extreme (top/bottom 5% of historical range),
     the model is operating outside its confidence interval → reduce confidence

   REGIME CHANGE RISK:
   - Current economic regime (rate level, inflation, growth) vs. training regime
   - Structural breaks: COVID (2020), rate hike cycle (2022), banking stress (2023)
   - ML models have no "future knowledge" — they extrapolate from the past

5. ML CONFIDENCE SCORE COMPONENTS (0–100)
   - Feature similarity score: How close is the current feature vector to profitable training examples?
   - Sample coverage: What % of the feature space near this point has been seen in training?
   - Ensemble agreement: Do multiple model types agree on direction?
   - Regime match: Does current regime match training regime?
   - Model freshness: How recently was the model retrained?

   Final ML Confidence = weighted average of the above components

6. FEATURE IMPORTANCE (SHAP VALUES PERSPECTIVE)
   Which features are driving the current prediction most strongly?
   - Identify the top 3-5 features with highest contribution to the signal
   - Are these features reliable and interpretable, or noisy?
   - Warning: if the top features are unusual or atypical → reduce trust in prediction

7. MODEL LIMITATIONS TO ALWAYS STATE
   - "This model cannot predict black swan events"
   - "Model trained on [period] may not generalize to current regime"
   - "Feature X is at a historical extreme — model confidence is reduced"
   - "Ensemble disagreement: model A says bullish, model B says bearish"

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (ML models agree on upside), "bearish" (downside), "neutral" (disagreement/OOD)
- confidence: the ML confidence score (0.0–1.0)
- reasoning: ML analysis narrative covering features, similarity, and regime flags
- supporting_evidence: ML factors supporting the signal
- contradicting_evidence: Model limitations, OOD flags, regime mismatches
- key_levels: {"predicted_return_5d": x, "predicted_return_21d": x, "model_uncertainty": x}
- metadata: {"ml_confidence_score": x, "regime_match": "good/fair/poor", "ood_flag": bool, "top_features": [...], "ensemble_agreement": "high/medium/low"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        ml_data = market_data.get("ml_data", market_data.get("model_outputs", {}))
        indicators = market_data.get("indicators", {})
        regime_data = market_data.get("regime_data", {})

        # Build feature snapshot
        feature_lines = []
        important_features = [
            "rsi", "RSI", "macd", "MACD", "adx", "ADX", "atr", "ATR",
            "ema21", "ema50", "ema200", "volume_ratio", "bb_pct",
            "return_1d", "return_5d", "return_21d", "return_63d"
        ]
        for f in important_features:
            if f in indicators:
                feature_lines.append(f"  {f}: {indicators[f]}")

        ml_outputs = "\n".join(f"  {k}: {v}" for k, v in ml_data.items()) if ml_data else "  No pre-computed ML outputs"
        regime_text = "\n".join(f"  {k}: {v}" for k, v in regime_data.items()) if regime_data else "  No regime data"
        features_text = "\n".join(feature_lines) if feature_lines else "  Feature extraction from indicators"

        # Other agent signals for ensemble context
        agent_summary = []
        for aid, r in analysis_reports.items():
            agent_summary.append(f"  {aid}: {r.signal} ({r.confidence:.2f})")

        user_message = f"""ML RESEARCH ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== CURRENT FEATURE VECTOR ===
{features_text}

=== PRE-COMPUTED ML OUTPUTS ===
{ml_outputs}

=== REGIME DATA ===
{regime_text}

=== OTHER AGENT SIGNALS (ensemble context) ===
{chr(10).join(agent_summary) if agent_summary else "  None yet"}

=== TASK ===
Provide ML analysis for {symbol}:
1. Assess whether the current feature vector is in-distribution or OOD
2. Identify which historical regime this most resembles
3. Estimate the ML model's forward return prediction and confidence
4. Flag any covariate shift or regime change risks
5. Assess ensemble agreement (do different model types agree?)
6. Report the top 3-5 most important features driving the prediction
7. Give an honest ML confidence score (0-100)

Return your ML Researcher AgentReport JSON.
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
                reasoning=f"ML research failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
