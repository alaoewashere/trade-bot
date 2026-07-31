'use client';

import React, { useState } from 'react';
import TopNav from './TopNav';
import SideNav from './SideNav';
import ViewRouter from './ViewRouter';
import SearchModal from './SearchModal';
import NotificationsPanel from './NotificationsPanel';

const SIDEBAR_W = 280;
const SIDEBAR_COLLAPSED_W = 72;
const TOPNAV_H = 72;

export default function AppLayout() {
  const [activeView, setActiveView] = useState('dashboard');
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const sw = collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W;

  return (
    <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `${sw}px 1fr`,
          gridTemplateRows: `${TOPNAV_H}px 1fr`,
          gridTemplateAreas: `"sidebar topnav" "sidebar main"`,
          height: '100vh',
          width: '100vw',
          overflow: 'hidden',
          background: '#0B1020',
          transition: 'grid-template-columns 0.25s ease',
        }}
      >
        {/* Sidebar */}
        <div style={{ gridArea: 'sidebar', overflow: 'hidden' }}>
          <SideNav
            collapsed={collapsed}
            onToggle={() => setCollapsed(c => !c)}
            activeView={activeView}
            setActiveView={setActiveView}
          />
        </div>

        {/* Top navigation */}
        <div style={{ gridArea: 'topnav', overflow: 'hidden' }}>
          <TopNav
            activeView={activeView}
            onSearchOpen={() => setSearchOpen(true)}
            onNotifOpen={() => setNotifOpen(true)}
          />
        </div>

        {/* Main scrollable content */}
        <main style={{ gridArea: 'main', overflowY: 'auto', overflowX: 'hidden' }}>
          <ViewRouter activeView={activeView} />
        </main>
      </div>

      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      <NotificationsPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  );
}
