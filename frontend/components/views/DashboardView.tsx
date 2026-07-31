'use client';

import React from 'react';
import { motion } from 'framer-motion';
import PlanetHero from '@/components/space/PlanetHero';
import CommandCenter from '@/components/space/CommandCenter';
import AgentWorkers from '@/components/space/AgentWorkers';

export default function DashboardView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: 24, paddingBottom: 48 }}
    >
      <PlanetHero />
      <CommandCenter />
      <AgentWorkers />
    </motion.div>
  );
}
