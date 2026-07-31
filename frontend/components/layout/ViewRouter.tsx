'use client';

import React from 'react';
import DashboardView from '@/components/views/DashboardView';
import MarketsView from '@/components/views/MarketsView';
import ChartsView from '@/components/views/ChartsView';
import AgentsView from '@/components/views/AgentsView';
import PortfolioView from '@/components/views/PortfolioView';
import StrategiesView from '@/components/views/StrategiesView';
import ResearchView from '@/components/views/ResearchView';
import JournalView from '@/components/views/JournalView';
import NewsView from '@/components/views/NewsView';
import PerformanceView from '@/components/views/PerformanceView';
import BacktestingView from '@/components/views/BacktestingView';
import PaperTradingView from '@/components/views/PaperTradingView';
import LiveTradingView from '@/components/views/LiveTradingView';
import BrokerConnectionsView from '@/components/views/BrokerConnectionsView';
import ExecutionHistoryView from '@/components/views/ExecutionHistoryView';
import SettingsView from '@/components/views/SettingsView';
import RiskCenterView from '@/components/views/RiskCenterView';

export default function ViewRouter({ activeView }: { activeView: string }) {
  switch (activeView) {
    case 'dashboard':           return <DashboardView />;
    case 'markets':              return <MarketsView />;
    case 'charts':                return <ChartsView />;
    case 'charts2':               return <ChartsView />;
    case 'agents':                return <AgentsView />;
    case 'portfolio':             return <PortfolioView />;
    case 'risk-center':           return <RiskCenterView />;
    case 'strategies':            return <StrategiesView />;
    case 'research':              return <ResearchView />;
    case 'journal':               return <JournalView />;
    case 'news':                  return <NewsView />;
    case 'performance':           return <PerformanceView />;
    case 'backtesting':           return <BacktestingView />;
    case 'paper':                 return <PaperTradingView />;
    case 'live-trading':          return <LiveTradingView />;
    case 'broker-connections':    return <BrokerConnectionsView />;
    case 'execution-history':     return <ExecutionHistoryView />;
    case 'settings':              return <SettingsView />;
    default:                      return <DashboardView />;
  }
}
