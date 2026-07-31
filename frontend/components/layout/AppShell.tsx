'use client';

import React from 'react';
import TopBar from './TopBar';
import Sidebar from './Sidebar';
import { useAppStore } from '@/lib/store';

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const { sidebarCollapsed } = useAppStore();
  const sidebarWidth = sidebarCollapsed ? 68 : 280;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0B1020', overflow: 'hidden' }}>
      {/* Top bar — natural flow, shrinks to its height */}
      <TopBar />

      {/* Body row — sidebar + scrollable main */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <Sidebar />

        {/* Main scrollable area */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            minWidth: 0,
            transition: 'all 0.3s ease',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
