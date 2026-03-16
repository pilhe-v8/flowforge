import { apiClient } from './client';

export async function fetchTemplates(): Promise<Array<{ slug: string; name: string }>> {
  const res = await apiClient.get<{ templates: Array<{ slug: string; name: string }> }>('/templates');
  return res.data.templates;
}
