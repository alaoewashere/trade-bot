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
  },

  system: {
    killSwitch: () =>
      fetchAPI<{ success: boolean; message: string }>('/system/kill', { method: 'POST' }),
    getStatus: () => fetchAPI<{ status: string; uptime: number }>('/system/status'),
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
