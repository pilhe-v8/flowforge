/**
 * Fetch available LiteLLM model IDs from the backend proxy.
 * Falls back to ["default", "azure-fallback"] if the call fails.
 */
export async function fetchAvailableModels(): Promise<string[]> {
  try {
    const token = localStorage.getItem('flowforge_token') ?? '';
    const res = await fetch('/api/v1/models', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json() as { data: { id: string }[] };
    return data.data.map((m) => m.id);
  } catch {
    // Graceful fallback — model picker still works offline
    return ['default', 'azure-fallback'];
  }
}
