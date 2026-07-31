import { create } from 'zustand';

interface AppStore {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  activeSymbol: string;
  setActiveSymbol: (s: string) => void;
  activeView: string;
  setActiveView: (v: string) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  activeSymbol: 'BTC/USDT',
  setActiveSymbol: (s) => set({ activeSymbol: s }),
  activeView: 'dashboard',
  setActiveView: (v) => set({ activeView: v }),
}));
