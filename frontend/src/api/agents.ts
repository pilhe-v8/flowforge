import { apiClient } from './client';
import { AgentProfile } from '../types';

export async function fetchAgents(): Promise<AgentProfile[]> {
  const res = await apiClient.get<{ agents: AgentProfile[] }>('/agents');
  return res.data.agents;
}
