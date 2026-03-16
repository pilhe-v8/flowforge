import { create } from 'zustand';
import { ToolSchema, AgentProfile } from '../types';
import { fetchToolCatalogue } from '../api/tools';
import { fetchAgents as fetchAgentsApi } from '../api/agents';

interface ToolCatalogueState {
  tools: ToolSchema[];
  agents: AgentProfile[];
  loading: boolean;
  error: string | null;
  fetchCatalogue: () => Promise<void>;
  fetchAgents: () => Promise<void>;
}

export const useToolCatalogueStore = create<ToolCatalogueState>((set) => ({
  tools: [],
  agents: [],
  loading: false,
  error: null,

  fetchCatalogue: async () => {
    set({ loading: true, error: null });
    try {
      const tools = await fetchToolCatalogue();
      set({ tools, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchAgents: async () => {
    set({ loading: true, error: null });
    try {
      const agents = await fetchAgentsApi();
      set({ agents, loading: false });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },
}));
