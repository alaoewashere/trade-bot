import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'HEDGE-AI // Institutional Trading System',
  description: 'Multi-Agent Hedge Fund AI — Institutional Grade',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
