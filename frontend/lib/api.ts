const BASE_URL = '/api';

export interface AgentState {
  agent_id: string;
  agent_name: string;
  display_name: string;
  department: string;
  status: 'idle' | 'analyzing' | 'debating';
  signal: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  last_message?: string;
  last_updated?: string;
}

export interface TradeSignal {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_zone: [number, number];
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  confidence: number;
  agents_agreed: number;
  agents_total: number;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export interface Prediction {
  timeframe: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  bull_prob: number;
  bear_prob: number;
  neutral_prob: number;
}

export interface PortfolioMetrics {
  total_pnl: number;
  daily_pnl: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  active_positions: number;
  total_agents: number;
  active_agents: number;
}

export interface RiskAssessment {
  assessment_id: string;
  symbol: string;
  direction: string;
  approved: boolean;
  position_size_usd: number;
  position_size_units: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  max_risk_usd: number;
  portfolio_heat_pct: number;
  var_95: number;
  cvar_95: number;
  kelly_fraction: number;
  expected_value_usd: number;
  risk_category: 'very_low' | 'low' | 'medium' | 'high' | 'extreme';
  correlation_check: boolean;
  liquidity_check: boolean;
  rejection_reasons: string[];
  consensus_confidence_pct: number | null;
  created_at: string;
}

export interface RiskHeatmapEntry {
  symbol: string;
  position_size_usd: number;
  risk_usd: number;
  heat_pct: number;
  var_95_usd: number;
  direction: string;
}

export interface PortfolioHeatmap {
  total_heat_pct: number;
  equity_usd: number;
  positions: RiskHeatmapEntry[];
  calculated_at: string;
}

export interface VaRSummary {
  portfolio_var_95_usd: number;
  portfolio_var_99_usd: number;
  worst_position_var_usd: string | null;
  total_positions_value_usd: number;
  methodology: string;
  calculated_at: string;
}

export interface JournalEntry {
  id: string;
  trade_id: string | null;
  symbol: string;
  direction: string;
  entry_price: number | null;
  exit_price: number | null;
  opened_at: string | null;
  closed_at: string | null;
  outcome: 'WIN' | 'LOSS' | 'BE' | null;
  pnl_usd: number | null;
  ai_consensus_direction: string | null;
  ai_confidence_pct: number | null;
  agent_opinions: unknown[];
  market_regime: string | null;
  risk_score: number | null;
  emotional_notes: string | null;
  execution_notes: string | null;
  lessons_learned: string | null;
  created_at: string;
}

export interface ScoredEvidenceItem {
  label: string;
  score: number;
  agent_id?: string;
  [key: string]: unknown;
}

export interface ForecastExplanation {
  forecast_id: string;
  symbol: string;
  timeframe: string;
  direction: string;
  confidence_pct: number;
  final_thesis: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  departments: {
    department: string;
    agents: {
      agent_id: string;
      signal: string;
      confidence_pct: number;
      reasoning: string | null;
      outcome: string;
      decided_at: string;
    }[];
    avg_confidence_pct: number;
    dominant_signal: string;
  }[];
  agreement: {
    total_agents: number;
    agreeing_agents: number;
    disagreeing_agents: number;
    agreement_pct: number;
    dissenting_agent_ids: string[];
  };
  generated_at: string;
  // --- Phase 4 additions (additive) ---
  supporting_evidence_scored: ScoredEvidenceItem[];
  contradicting_evidence_scored: ScoredEvidenceItem[];
  bullish_score: number;
  bearish_score: number;
  net_ai_score: number;
}

// --- Phase 4: prediction history / validation ledger ---

export interface ForecastHistoryEntry {
  forecast_id: string;
  symbol: string;
  timeframe: string;
  created_at: string;
  expiry_at: string;
  price_at_creation: number;
  direction: string;
  confidence_pct: number;
  bull_probability: number;
  bear_probability: number;
  predicted_low: number;
  predicted_high: number;
  market_regime: string | null;
  reasoning_summary: string | null;
  evaluated: boolean;
  outcome: 'win' | 'loss' | 'expired' | 'pending' | null;
  actual_price_at_expiry: number | null;
  actual_direction: string | null;
  direction_correct: boolean | null;
  range_hit: boolean | null;
  absolute_error_pct: number | null;
  duration_minutes: number | null;
  high_touched: number | null;
  low_touched: number | null;
  mfe: number | null;
  mae: number | null;
  tp_price: number | null;
  sl_price: number | null;
  tp_hit: boolean | null;
  sl_hit: boolean | null;
}

export interface ForecastHistoryPage {
  total: number;
  limit: number;
  offset: number;
  items: ForecastHistoryEntry[];
}

// --- Phase 5: chart foundation (candles) + the "current forecast" shape ---

export interface ForecastResponse {
  forecast_id: string;
  symbol: string;
  timeframe: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  confidence_pct: number;
  bull_probability: number;
  bear_probability: number;
  neutral_probability: number;
  predicted_low: number;
  predicted_high: number;
  risk_score: number;
  market_regime: string;
  model_contributions: Record<string, number>;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  created_at: string;
  expiry_at: string;
}

export interface DashboardEntry {
  timeframe: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  confidence_pct: number;
  bull_probability: number;
  bear_probability: number;
  predicted_low: number;
  predicted_high: number;
  risk_score: number;
  market_regime: string;
  created_at: string;
  expiry_at: string;
  forecast_id: string | null;
}

export interface ForecastDashboard {
  symbol: string;
  generated_at: string;
  overall_bias: string;
  overall_confidence_pct: number;
  timeframes: DashboardEntry[];
}

export interface Candle {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandlesResponse {
  symbol: string;
  timeframe: string;
  candles: Candle[];
}

// --- Phase 4: agent performance ---

export interface AgentPerformance {
  agent_id: string;
  total_reports: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  no_signal_count: number;
  avg_confidence: number;
  accuracy_pct: number | null;
  brier_score: number | null;
  measured_at: string;
  win_rate_pct: number | null;
  avg_return_pct: number | null;
  reliability_score: number | null;
  current_form_pct: number | null;
  all_time_accuracy_pct: number | null;
  longest_winning_streak: number;
  longest_losing_streak: number;
  last_100_predictions: string[];
  success_by_regime: Record<string, number>;
  success_by_timeframe: Record<string, number>;
  success_by_asset: Record<string, number>;
  resolved_decisions: number;
  pending_decisions: number;
}

export interface AgentRankingEntry {
  agent_id: string;
  department: string;
  reliability_score: number;
  accuracy_pct: number | null;
  win_rate_pct: number | null;
  resolved_decisions: number;
  current_form_pct: number | null;
}

export interface DayPnl {
  date: string;
  pnl_usd: number;
}

export interface TradeStats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  win_rate_pct: number;
  total_pnl_usd: number;
  avg_win_usd: number;
  avg_loss_usd: number;
  profit_factor: number;
  avg_risk_reward: number;
  largest_win_usd: number;
  largest_loss_usd: number;
  avg_duration_minutes: number;
  measured_at: string;
  expectancy_usd: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  max_drawdown_pct: number;
  avg_trade_duration_minutes: number;
  best_day: DayPnl | null;
  worst_day: DayPnl | null;
  equity_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  daily_return_pct: number;
  weekly_return_pct: number;
  monthly_return_pct: number;
}

export interface EquityCurvePoint {
  timestamp: string;
  cumulative_pnl_usd: number;
  drawdown_pct: number;
}

export interface CalendarDay {
  date: string;
  pnl_usd: number;
  trade_count: number;
}

export interface BacktestRunRequest {
  symbol: string;
  timeframe: string;
  strategy?: string | null;
  date_range_start: string;
  date_range_end: string;
  notes?: string | null;
}

export interface BacktestRunSummary {
  id: string;
  created_at: string;
  symbol: string;
  timeframe: string;
  strategy_name: string | null;
  date_range_start: string;
  date_range_end: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  notes: string | null;
}

export interface BacktestTradeSample {
  forecast_id: string;
  opened_at: string | null;
  closed_at: string | null;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  exit_price: number;
  return_pct: number;
  pnl_usd: number;
  confidence_pct: number;
  market_regime: string | null;
  holding_minutes: number | null;
}

export interface BacktestResults {
  num_trades: number;
  num_forecasts_considered: number;
  total_return_pct: number;
  annual_return_pct: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  profit_factor: number;
  avg_trade_pnl_usd: number;
  avg_holding_time_minutes: number | null;
  best_trade: BacktestTradeSample | null;
  worst_trade: BacktestTradeSample | null;
  longest_winning_streak: number;
  longest_losing_streak: number;
  equity_curve: { timestamp: string; cumulative_pnl_usd: number; drawdown_pct: number }[];
  trade_distribution: { bucket: string; count: number }[];
  monthly_heatmap: { month: string; pnl_usd: number }[];
  performance_by_regime: { regime: string; num_trades: number; total_pnl_usd: number; win_rate_pct: number }[];
  performance_by_timeframe: { timeframe: string | null; num_trades: number; total_pnl_usd: number }[];
  note?: string;
}

export interface BacktestRunDetail extends BacktestRunSummary {
  results: BacktestResults;
  error_message: string | null;
  created_by: string | null;
}

// --- Phase 3: Portfolio / Markets / Alerts ---

export interface PortfolioSnapshot {
  equity_usd: number;
  cash_usd: number;
  open_positions_value_usd: number;
  unrealised_pnl_usd: number;
  unrealised_pnl_pct: number;
  total_pnl_usd: number;
  total_pnl_pct: number;
  portfolio_heat_pct: number;
  open_positions_count: number;
  win_rate_pct: number;
  daily_pnl_usd: number;
  weekly_pnl_usd: number;
  monthly_pnl_usd: number;
  max_drawdown_pct: number;
  sharpe_ratio: number | null;
  snapshot_at: string;
}

export interface AllocationBreakdown {
  by_symbol: Record<string, number>;
  by_direction: Record<string, number>;
  by_broker: Record<string, number>;
  diversification_score: number;
  calculated_at: string;
}

export interface RiskExposureEntry {
  symbol: string;
  direction: string;
  position_size_usd: number;
  risk_usd: number;
  risk_pct_of_equity: number;
  stop_loss: number;
  entry_price: number;
}

export interface RiskExposure {
  total_exposure_usd: number;
  total_risk_usd: number;
  portfolio_heat_pct: number;
  positions: RiskExposureEntry[];
  measured_at: string;
}

export interface OpenPosition {
  trade_id: string;
  symbol: string;
  direction: string;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  unrealised_pnl_usd: number | null;
  unrealised_pnl_pct: number | null;
  stop_loss: number;
  take_profit_levels: number[];
  broker_order_id: string | null;
  opened_at: string;
  duration_minutes: number;
}

export interface TradeRecord {
  trade_id: string;
  symbol: string;
  direction: string;
  entry_type: string;
  entry_price: number | null;
  filled_price: number | null;
  quantity: number;
  stop_loss: number;
  take_profit_levels: number[];
  broker: string;
  broker_order_id: string | null;
  status: string;
  pnl_usd: number | null;
  pnl_pct: number | null;
  commission: number;
  slippage: number;
  consensus_direction: string | null;
  consensus_confidence_pct: number | null;
  approval_id: string | null;
  opened_at: string;
  closed_at: string | null;
  notes: string;
}

export interface LiveTicker {
  symbol: string;
  price: number;
  change_24h_pct: number;
  high_24h: number;
  low_24h: number;
  volume_24h_quote: number;
  updated_at: string;
}

export interface OrderBookResponse {
  symbol: string;
  bids: { price: number; quantity: number }[];
  asks: { price: number; quantity: number }[];
  best_bid: number;
  best_ask: number;
  spread_bps: number;
  fetched_at: string;
}

export interface FundingResponse {
  symbol: string;
  applicable: boolean;
  funding_rate_pct: number | null;
  next_funding_time: string | null;
  open_interest: number | null;
  note: string | null;
}

export interface FearGreedResponse {
  value: number;
  classification: string;
  updated_at: string;
  source: string;
}

export interface ProviderGatedResponse {
  provider_configured: boolean;
  data: Record<string, unknown>[];
  message: string;
}

export interface AlertRecord {
  id: string;
  created_at: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  symbol: string | null;
  message: string;
  payload: Record<string, unknown>;
  acknowledged: boolean;
  acknowledged_at: string | null;
}

export interface UnreadCountResponse {
  unread_count: number;
  by_severity: Record<string, number>;
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  agents: {
    getAll: () => fetchAPI<AgentState[]>('/agents'),
    getById: (id: string) => fetchAPI<AgentState>(`/agents/${id}`),
    getPerformance: (id: string) => fetchAPI<AgentPerformance>(`/agents/${id}/performance`),
    getRankings: (params?: { min_decisions?: number }) => {
      const qs = new URLSearchParams();
      if (params?.min_decisions !== undefined) qs.set('min_decisions', String(params.min_decisions));
      const q = qs.toString();
      return fetchAPI<AgentRankingEntry[]>(`/agents/rankings${q ? `?${q}` : ''}`);
    },
  },

  trading: {
    getSignals: () => fetchAPI<TradeSignal[]>('/trading/signals'),
    approveSignal: (id: string) =>
      fetchAPI<{ success: boolean }>(`/trading/signals/${id}/approve`, { method: 'POST' }),
    rejectSignal: (id: string) =>
      fetchAPI<{ success: boolean }>(`/trading/signals/${id}/reject`, { method: 'POST' }),
    getPredictions: (symbol?: string) =>
      fetchAPI<Prediction[]>(`/trading/predictions${symbol ? `?symbol=${symbol}` : ''}`),
  },

  portfolio: {
    getMetrics: () => fetchAPI<PortfolioMetrics>('/portfolio/metrics'),
    getSnapshot: () => fetchAPI<PortfolioSnapshot>('/portfolio'),
    getAllocation: () => fetchAPI<AllocationBreakdown>('/portfolio/allocation'),
    getRiskExposure: () => fetchAPI<RiskExposure>('/portfolio/risk-exposure'),
    getHistory: (params?: { interval?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.interval) qs.set('interval', params.interval);
      if (params?.limit) qs.set('limit', String(params.limit));
      const q = qs.toString();
      return fetchAPI<unknown[]>(`/portfolio/history${q ? `?${q}` : ''}`);
    },
    getDrawdown: () => fetchAPI<unknown>('/portfolio/drawdown'),
  },

  risk: {
    getAssessments: (params?: { symbol?: string; approved_only?: boolean; rejected_only?: boolean; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.approved_only) qs.set('approved_only', 'true');
      if (params?.rejected_only) qs.set('rejected_only', 'true');
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<RiskAssessment[]>(`/risk/assessments${q ? `?${q}` : ''}`);
    },
    getHeatmap: () => fetchAPI<PortfolioHeatmap>('/risk/heatmap'),
    getVar: () => fetchAPI<VaRSummary>('/risk/var'),
  },

  journal: {
    list: (params?: { symbol?: string; outcome?: string; since?: string; until?: string; search?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.outcome) qs.set('outcome', params.outcome);
      if (params?.since) qs.set('since', params.since);
      if (params?.until) qs.set('until', params.until);
      if (params?.search) qs.set('search', params.search);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<JournalEntry[]>(`/journal${q ? `?${q}` : ''}`);
    },
    getById: (id: string) => fetchAPI<JournalEntry>(`/journal/${id}`),
    create: (entry: Partial<JournalEntry> & { symbol: string; direction: string }) =>
      fetchAPI<JournalEntry>('/journal', { method: 'POST', body: JSON.stringify(entry) }),
    update: (id: string, patch: Pick<Partial<JournalEntry>, 'emotional_notes' | 'execution_notes' | 'lessons_learned' | 'outcome'>) =>
      fetchAPI<JournalEntry>(`/journal/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  },

  forecasts: {
    explain: (forecastId: string) => fetchAPI<ForecastExplanation>(`/forecasts/${forecastId}/explain`),
    getById: (forecastId: string) => fetchAPI<ForecastResponse>(`/forecasts/${forecastId}`),
    getLatest: (symbol: string, timeframe = '1h') =>
      fetchAPI<ForecastResponse>(`/forecasts?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`),
    getDashboard: (symbol: string) =>
      fetchAPI<ForecastDashboard>(`/forecasts/dashboard?symbol=${encodeURIComponent(symbol)}`),
    history: (params?: {
      symbol?: string;
      timeframe?: string;
      outcome?: string;
      since?: string;
      until?: string;
      limit?: number;
      offset?: number;
    }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.timeframe) qs.set('timeframe', params.timeframe);
      if (params?.outcome) qs.set('outcome', params.outcome);
      if (params?.since) qs.set('since', params.since);
      if (params?.until) qs.set('until', params.until);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<ForecastHistoryPage>(`/forecasts/history${q ? `?${q}` : ''}`);
    },
  },

  trades: {
    list: (params?: { symbol?: string; direction?: string; status?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.direction) qs.set('direction', params.direction);
      if (params?.status) qs.set('status', params.status);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<TradeRecord[]>(`/trades${q ? `?${q}` : ''}`);
    },
    listOpen: () => fetchAPI<OpenPosition[]>('/trades/open'),
    stats: (params?: { symbol?: string; since?: string }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.since) qs.set('since', params.since);
      const q = qs.toString();
      return fetchAPI<TradeStats>(`/trades/stats${q ? `?${q}` : ''}`);
    },
    equityCurve: (params?: { symbol?: string; since?: string }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.since) qs.set('since', params.since);
      const q = qs.toString();
      return fetchAPI<EquityCurvePoint[]>(`/trades/equity-curve${q ? `?${q}` : ''}`);
    },
    calendar: (params?: { symbol?: string; since?: string; until?: string }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.since) qs.set('since', params.since);
      if (params?.until) qs.set('until', params.until);
      const q = qs.toString();
      return fetchAPI<CalendarDay[]>(`/trades/calendar${q ? `?${q}` : ''}`);
    },
  },

  backtest: {
    run: (req: BacktestRunRequest) =>
      fetchAPI<BacktestRunDetail>('/backtest/run', { method: 'POST', body: JSON.stringify(req) }),
    list: (params?: { symbol?: string; status?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.status) qs.set('status', params.status);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<BacktestRunSummary[]>(`/backtest/runs${q ? `?${q}` : ''}`);
    },
    get: (id: string) => fetchAPI<BacktestRunDetail>(`/backtest/runs/${id}`),
  },

  system: {
    killSwitch: () =>
      fetchAPI<{ success: boolean; message: string }>('/system/kill', { method: 'POST' }),
    getStatus: () => fetchAPI<{ status: string; uptime: number }>('/system/status'),
  },

  markets: {
    getLive: (symbols?: string[]) =>
      fetchAPI<LiveTicker[]>(`/markets/live${symbols?.length ? `?symbols=${symbols.join(',')}` : ''}`),
    getOrderbook: (symbol: string, depth = 20) =>
      fetchAPI<OrderBookResponse>(`/markets/${encodeURIComponent(symbol)}/orderbook?depth=${depth}`),
    getFunding: (symbol: string) =>
      fetchAPI<FundingResponse>(`/markets/${encodeURIComponent(symbol)}/funding`),
    getCandles: (symbol: string, timeframe = '1h', limit = 300) =>
      fetchAPI<CandlesResponse>(`/markets/${encodeURIComponent(symbol)}/candles?timeframe=${timeframe}&limit=${limit}`),
    getFearGreed: () => fetchAPI<FearGreedResponse>('/markets/fear-greed'),
    getWhaleActivity: () => fetchAPI<ProviderGatedResponse>('/markets/whale-activity'),
    getExchangeFlows: () => fetchAPI<ProviderGatedResponse>('/markets/exchange-flows'),
  },

  alerts: {
    list: (params?: { alert_type?: string; severity?: string; acknowledged?: boolean; symbol?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.alert_type) qs.set('alert_type', params.alert_type);
      if (params?.severity) qs.set('severity', params.severity);
      if (params?.acknowledged !== undefined) qs.set('acknowledged', String(params.acknowledged));
      if (params?.symbol) qs.set('symbol', params.symbol);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      const q = qs.toString();
      return fetchAPI<AlertRecord[]>(`/alerts${q ? `?${q}` : ''}`);
    },
    acknowledge: (id: string) =>
      fetchAPI<AlertRecord>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
    unreadCount: () => fetchAPI<UnreadCountResponse>('/alerts/unread-count'),
  },
};

// Mock data for fallback rendering when backend is unavailable
export const MOCK_AGENTS: AgentState[] = [
  { agent_id: 'cio_agent', agent_name: 'cio_agent', display_name: 'Chief Investment Officer', department: 'executive', status: 'analyzing', signal: 'bullish', confidence: 78 },
  { agent_id: 'cro_agent', agent_name: 'cro_agent', display_name: 'Chief Risk Officer', department: 'executive', status: 'idle', signal: 'neutral', confidence: 55 },
  { agent_id: 'portfolio_manager', agent_name: 'portfolio_manager', display_name: 'Portfolio Manager', department: 'executive', status: 'debating', signal: 'bullish', confidence: 82 },
  { agent_id: 'macro_economist', agent_name: 'macro_economist', display_name: 'Macro Economist', department: 'market_intelligence', status: 'analyzing', signal: 'bearish', confidence: 67 },
  { agent_id: 'news_analyst', agent_name: 'news_analyst', display_name: 'News Analyst', department: 'market_intelligence', status: 'analyzing', signal: 'bullish', confidence: 71 },
  { agent_id: 'sentiment_analyst', agent_name: 'sentiment_analyst', display_name: 'Sentiment Analyst', department: 'market_intelligence', status: 'debating', signal: 'bullish', confidence: 64 },
  { agent_id: 'regulation_analyst', agent_name: 'regulation_analyst', display_name: 'Regulation Analyst', department: 'market_intelligence', status: 'idle', signal: 'neutral', confidence: 50 },
  { agent_id: 'trend_analyst', agent_name: 'trend_analyst', display_name: 'Trend Analyst', department: 'technical', status: 'analyzing', signal: 'bullish', confidence: 85 },
  { agent_id: 'price_action', agent_name: 'price_action', display_name: 'Price Action Specialist', department: 'technical', status: 'analyzing', signal: 'bullish', confidence: 79 },
  { agent_id: 'smc_expert', agent_name: 'smc_expert', display_name: 'SMC Expert', department: 'technical', status: 'debating', signal: 'bearish', confidence: 62 },
  { agent_id: 'wyckoff_analyst', agent_name: 'wyckoff_analyst', display_name: 'Wyckoff Analyst', department: 'technical', status: 'analyzing', signal: 'bullish', confidence: 73 },
  { agent_id: 'elliott_wave', agent_name: 'elliott_wave', display_name: 'Elliott Wave Expert', department: 'technical', status: 'idle', signal: 'neutral', confidence: 58 },
  { agent_id: 'volume_profile', agent_name: 'volume_profile', display_name: 'Volume Profile Analyst', department: 'technical', status: 'analyzing', signal: 'bullish', confidence: 77 },
  { agent_id: 'market_structure', agent_name: 'market_structure', display_name: 'Market Structure Analyst', department: 'technical', status: 'debating', signal: 'bullish', confidence: 81 },
  { agent_id: 'quant_researcher', agent_name: 'quant_researcher', display_name: 'Quant Researcher', department: 'quantitative', status: 'analyzing', signal: 'bullish', confidence: 88 },
  { agent_id: 'probability_analyst', agent_name: 'probability_analyst', display_name: 'Probability Analyst', department: 'quantitative', status: 'analyzing', signal: 'bullish', confidence: 83 },
  { agent_id: 'ml_researcher', agent_name: 'ml_researcher', display_name: 'ML Researcher', department: 'quantitative', status: 'idle', signal: 'neutral', confidence: 52 },
  { agent_id: 'backtesting_expert', agent_name: 'backtesting_expert', display_name: 'Backtesting Expert', department: 'quantitative', status: 'analyzing', signal: 'bullish', confidence: 75 },
  { agent_id: 'hf_pattern_detector', agent_name: 'hf_pattern_detector', display_name: 'HF Pattern Detector', department: 'quantitative', status: 'analyzing', signal: 'bullish', confidence: 86 },
  { agent_id: 'options_flow_analyst', agent_name: 'options_flow_analyst', display_name: 'Options Flow Analyst', department: 'options', status: 'debating', signal: 'bullish', confidence: 79 },
  { agent_id: 'volatility_analyst', agent_name: 'volatility_analyst', display_name: 'Volatility Analyst', department: 'options', status: 'analyzing', signal: 'bearish', confidence: 66 },
  { agent_id: 'onchain_analyst', agent_name: 'onchain_analyst', display_name: 'On-Chain Analyst', department: 'crypto', status: 'analyzing', signal: 'bullish', confidence: 72 },
  { agent_id: 'funding_rate_analyst', agent_name: 'funding_rate_analyst', display_name: 'Funding Rate Analyst', department: 'crypto', status: 'idle', signal: 'bearish', confidence: 61 },
  { agent_id: 'momentum_trader', agent_name: 'momentum_trader', display_name: 'Momentum Trader', department: 'strategy', status: 'debating', signal: 'bullish', confidence: 84 },
  { agent_id: 'mean_reversion', agent_name: 'mean_reversion', display_name: 'Mean Reversion Specialist', department: 'strategy', status: 'analyzing', signal: 'bearish', confidence: 69 },
  { agent_id: 'range_specialist', agent_name: 'range_specialist', display_name: 'Range Specialist', department: 'strategy', status: 'idle', signal: 'neutral', confidence: 54 },
  { agent_id: 'scalping_expert', agent_name: 'scalping_expert', display_name: 'Scalping Expert', department: 'strategy', status: 'analyzing', signal: 'bullish', confidence: 76 },
  { agent_id: 'swing_specialist', agent_name: 'swing_specialist', display_name: 'Swing Specialist', department: 'strategy', status: 'debating', signal: 'bullish', confidence: 80 },
  { agent_id: 'position_expert', agent_name: 'position_expert', display_name: 'Position Expert', department: 'strategy', status: 'analyzing', signal: 'bullish', confidence: 74 },
  { agent_id: 'trade_planner', agent_name: 'trade_planner', display_name: 'Trade Planner', department: 'execution', status: 'debating', signal: 'bullish', confidence: 87 },
  { agent_id: 'execution_bot', agent_name: 'execution_bot', display_name: 'Execution Bot', department: 'execution', status: 'idle', signal: 'neutral', confidence: 90 },
  { agent_id: 'liquidity_analyst', agent_name: 'liquidity_analyst', display_name: 'Liquidity Analyst', department: 'execution', status: 'analyzing', signal: 'bullish', confidence: 70 },
  { agent_id: 'exit_manager', agent_name: 'exit_manager', display_name: 'Exit Manager', department: 'execution', status: 'idle', signal: 'neutral', confidence: 65 },
  { agent_id: 'performance_analyst', agent_name: 'performance_analyst', display_name: 'Performance Analyst', department: 'monitoring', status: 'analyzing', signal: 'bullish', confidence: 78 },
  { agent_id: 'journal_ai', agent_name: 'journal_ai', display_name: 'Journal AI', department: 'monitoring', status: 'idle', signal: 'neutral', confidence: 60 },
  { agent_id: 'learning_agent', agent_name: 'learning_agent', display_name: 'Learning Agent', department: 'monitoring', status: 'analyzing', signal: 'bullish', confidence: 68 },
  { agent_id: 'security_bot', agent_name: 'security_bot', display_name: 'Security Bot', department: 'security', status: 'idle', signal: 'neutral', confidence: 95 },
  { agent_id: 'emergency_bot', agent_name: 'emergency_bot', display_name: 'Emergency Bot', department: 'security', status: 'idle', signal: 'neutral', confidence: 98 },
  { agent_id: 'debate_moderator', agent_name: 'debate_moderator', display_name: 'Debate Moderator', department: 'coordination', status: 'debating', signal: 'neutral', confidence: 72 },
  { agent_id: 'consensus_engine', agent_name: 'consensus_engine', display_name: 'Consensus Engine', department: 'coordination', status: 'debating', signal: 'bullish', confidence: 76 },
];

export const MOCK_SIGNALS: TradeSignal[] = [
  {
    id: 'sig_001',
    symbol: 'BTC/USDT',
    direction: 'LONG',
    entry_zone: [67200, 67800],
    stop_loss: 65500,
    take_profit: 72000,
    risk_reward: 2.8,
    confidence: 82,
    agents_agreed: 31,
    agents_total: 40,
    status: 'pending',
    created_at: new Date(Date.now() - 120000).toISOString(),
  },
  {
    id: 'sig_002',
    symbol: 'ETH/USDT',
    direction: 'LONG',
    entry_zone: [3480, 3520],
    stop_loss: 3350,
    take_profit: 3850,
    risk_reward: 2.5,
    confidence: 76,
    agents_agreed: 28,
    agents_total: 40,
    status: 'pending',
    created_at: new Date(Date.now() - 240000).toISOString(),
  },
  {
    id: 'sig_003',
    symbol: 'SOL/USDT',
    direction: 'SHORT',
    entry_zone: [182, 185],
    stop_loss: 192,
    take_profit: 168,
    risk_reward: 1.9,
    confidence: 68,
    agents_agreed: 22,
    agents_total: 40,
    status: 'pending',
    created_at: new Date(Date.now() - 360000).toISOString(),
  },
];

export const MOCK_PREDICTIONS: Prediction[] = [
  { timeframe: '1m', direction: 'bullish', confidence: 71, bull_prob: 71, bear_prob: 18, neutral_prob: 11 },
  { timeframe: '3m', direction: 'bullish', confidence: 74, bull_prob: 74, bear_prob: 16, neutral_prob: 10 },
  { timeframe: '5m', direction: 'bullish', confidence: 78, bull_prob: 78, bear_prob: 14, neutral_prob: 8 },
  { timeframe: '15m', direction: 'bullish', confidence: 82, bull_prob: 82, bear_prob: 12, neutral_prob: 6 },
  { timeframe: '30m', direction: 'bullish', confidence: 79, bull_prob: 79, bear_prob: 13, neutral_prob: 8 },
  { timeframe: '1h', direction: 'bullish', confidence: 76, bull_prob: 76, bear_prob: 15, neutral_prob: 9 },
  { timeframe: '4h', direction: 'neutral', confidence: 55, bull_prob: 45, bear_prob: 40, neutral_prob: 15 },
  { timeframe: '1d', direction: 'bearish', confidence: 62, bull_prob: 28, bear_prob: 62, neutral_prob: 10 },
];

export const MOCK_PORTFOLIO: PortfolioMetrics = {
  total_pnl: 284750,
  daily_pnl: 18320,
  win_rate: 68.4,
  sharpe_ratio: 2.34,
  max_drawdown: -4.2,
  active_positions: 3,
  total_agents: 40,
  active_agents: 27,
};
