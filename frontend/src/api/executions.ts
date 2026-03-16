import { apiClient } from './client';
import { Execution, ExecutionDetail } from '../types';

export async function triggerExecution(workflowSlug: string, data: Record<string, unknown>): Promise<{ execution_id: string }> {
  const res = await apiClient.post<{ execution_id: string }>('/executions/trigger', {
    workflow_slug: workflowSlug,
    input_data: data,
  });
  return res.data;
}

export async function fetchExecution(executionId: string): Promise<Execution> {
  const res = await apiClient.get<Execution>(`/executions/${executionId}`);
  return res.data;
}

export async function fetchExecutionDetail(executionId: string): Promise<ExecutionDetail> {
  const resp = await apiClient.get<ExecutionDetail>(`/executions/${executionId}`);
  return resp.data;
}
