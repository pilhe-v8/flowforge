import { create } from 'zustand';
import { fetchAvailableModels } from '../api/models';

interface ModelsState {
  models: string[];
  loading: boolean;
  fetchModels: () => Promise<void>;
}

export const useModelsStore = create<ModelsState>((set) => ({
  models: ['default', 'azure-fallback'],
  loading: false,

  fetchModels: async () => {
    set({ loading: true });
    try {
      const models = await fetchAvailableModels();
      set({ models, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
