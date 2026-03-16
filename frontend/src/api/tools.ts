import { apiClient } from './client';
import { ToolSchema } from '../types';

export async function fetchToolCatalogue(): Promise<ToolSchema[]> {
  const res = await apiClient.get<{ tools: ToolSchema[] }>('/tools/catalogue');
  return res.data.tools;
}
