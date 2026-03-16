/**
 * Fetch available LiteLLM model IDs from the backend proxy.
 * Falls back to ["default", "azure-fallback"] if the call fails.
 */
import { apiClient } from './client';

export async function fetchAvailableModels(): Promise<string[]> {
  try {
    const res = await apiClient.get<{ data: { id: string }[] }>('/models');
    return res.data.data.map((m) => m.id);
  } catch {
    // Graceful fallback — model picker still works offline
    return ['default', 'azure-fallback'];
  }
}
