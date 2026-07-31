/**
 * Pine Script v5 generator for the "AI -> Pine Strategy" surface.
 *
 * Pure client-side function — no backend round-trip needed since the
 * caller already has entry/SL/TP/confidence from whatever fetched the
 * consensus/risk-assessment data (ConsensusPanel / TradeSignalPanel).
 *
 * IMPORTANT (see phase scope): there is no TradingView API for injecting
 * this script into a chart. The generated text is meant to be copied or
 * downloaded and pasted into TradingView's Pine Editor by the user.
 */

export interface PineSignalInput {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry: number;
  stop_loss: number;
  take_profit: number;
  confidence: number; // 0-100
}

function sanitizeStrategyName(symbol: string): string {
  return `AI Signal - ${symbol.replace('/', '')}`.slice(0, 60);
}

/**
 * Generates a Pine v5 strategy script that:
 *  - plots buy/sell arrows at the AI's entry
 *  - draws SL/TP as label.new annotations (fixed at generation-time price,
 *    not recalculated bar-to-bar — this is a snapshot of one AI signal, not
 *    a live-recalculating indicator)
 *  - submits a strategy.entry/strategy.exit pair with the SL/TP baked in
 *  - shades the background while a position derived from this signal would
 *    be open
 *  - raises an alertcondition so the user can wire a TradingView alert to it
 *
 * Validated (mentally, syntax-reviewed against Pine v5 docs) against both
 * a BUY/LONG and a SELL/SHORT case — see the two representative examples in
 * the module comment at the bottom of this file.
 */
export function generatePineScript(input: PineSignalInput): string {
  const { symbol, direction, entry, stop_loss, take_profit, confidence } = input;
  const isLong = direction === 'LONG';
  const strategyName = sanitizeStrategyName(symbol);
  const entryLabel = isLong ? 'Long Entry' : 'Short Entry';
  const exitFrom = isLong ? 'Long' : 'Short';
  const dirWord = isLong ? 'long' : 'short';

  return `//@version=5
strategy("${strategyName}", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// --- AI signal snapshot (generated client-side from the current consensus) ---
// symbol:     ${symbol}
// direction:  ${direction}
// entry:      ${entry}
// stop_loss:  ${stop_loss}
// take_profit:${take_profit}
// confidence: ${confidence}%
aiEntry      = ${entry}
aiStopLoss   = ${stop_loss}
aiTakeProfit = ${take_profit}
aiConfidence = ${confidence}

// --- Entry condition: price trading through the AI's entry level ---
${isLong
    ? 'longCondition = ta.crossover(close, aiEntry)'
    : 'shortCondition = ta.crossunder(close, aiEntry)'}

if (${isLong ? 'longCondition' : 'shortCondition'})
    strategy.entry("${entryLabel}", strategy.${dirWord})
    strategy.exit("Exit ${entryLabel}", "${entryLabel}", stop=aiStopLoss, limit=aiTakeProfit)

// --- Visual markers ---
plotshape(${isLong ? 'longCondition' : 'shortCondition'}, title="${dirWord.toUpperCase()} Signal",
     style=${isLong ? 'shape.triangleup' : 'shape.triangledown'},
     location=${isLong ? 'location.belowbar' : 'location.abovebar'},
     color=${isLong ? 'color.new(color.green, 0)' : 'color.new(color.red, 0)'},
     size=size.small)

// Draw the entry/SL/TP annotations once, on the most recent bar, rather
// than redrawing on every historical bar (barstate.islast is the standard
// Pine v5 idiom for a single "as of now" overlay).
if (barstate.islast)
    line.new(bar_index - 1, aiEntry, bar_index + 20, aiEntry, color=color.new(color.blue, 0), style=line.style_dashed)
    line.new(bar_index - 1, aiStopLoss, bar_index + 20, aiStopLoss, color=color.new(color.red, 0), style=line.style_dashed)
    line.new(bar_index - 1, aiTakeProfit, bar_index + 20, aiTakeProfit, color=color.new(color.green, 0), style=line.style_dashed)
    label.new(bar_index, aiEntry, "Entry: " + str.tostring(aiEntry) + "\\nConfidence: " + str.tostring(aiConfidence) + "%",
         style=label.style_label_left, color=color.new(color.blue, 70), textcolor=color.white, size=size.small)
    label.new(bar_index, aiStopLoss, "SL: " + str.tostring(aiStopLoss),
         style=label.style_label_left, color=color.new(color.red, 70), textcolor=color.white, size=size.small)
    label.new(bar_index, aiTakeProfit, "TP: " + str.tostring(aiTakeProfit),
         style=label.style_label_left, color=color.new(color.green, 70), textcolor=color.white, size=size.small)

// --- Background shading while a position from this strategy is open ---
bgcolor(strategy.position_size != 0 ? (strategy.position_size > 0 ? color.new(color.green, 92) : color.new(color.red, 92)) : na)

// --- Alert wiring ---
alertcondition(${isLong ? 'longCondition' : 'shortCondition'}, title="AI ${direction} Signal — ${symbol}",
     message="AI ${direction} signal on ${symbol}: entry ${entry}, SL ${stop_loss}, TP ${take_profit} (confidence ${confidence}%)")
`;
}

export function pineScriptFilename(symbol: string): string {
  return `ai-signal-${symbol.replace('/', '-').toLowerCase()}.pine`;
}

export function tradingViewChartUrl(symbol: string): string {
  // TradingView's public chart URL format expects EXCHANGE:SYMBOL — we don't
  // know the user's preferred exchange, so BINANCE is used as the common
  // default for the crypto pairs this platform trades.
  const tvSymbol = `BINANCE:${symbol.replace('/', '')}`;
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`;
}

/*
 * Representative validation cases (syntax-reviewed manually, not executed —
 * there is no Pine Script compiler available in this environment):
 *
 * 1) LONG  BTC/USDT entry=67500 sl=65500 tp=72000 confidence=82
 *    -> ta.crossover(close, aiEntry); strategy.entry(..., strategy.long);
 *       strategy.exit("Exit Long Entry", "Long Entry", stop=65500, limit=72000)
 *
 * 2) SHORT SOL/USDT entry=183   sl=192   tp=168   confidence=68
 *    -> ta.crossunder(close, aiEntry); strategy.entry(..., strategy.short);
 *       strategy.exit("Exit Short Entry", "Short Entry", stop=192, limit=168)
 *
 * Both follow the documented Pine v5 strategy.exit(id, from_entry, stop, limit)
 * signature and use only str.tostring/label.new/line.new/plotshape/bgcolor/
 * alertcondition calls that exist in the v5 built-in namespace.
 */
