import { apiClient } from './client';
import { ExecutionDetail, ExecutionsListResponse } from '../types';

export async function triggerExecution(workflowSlug: string, data: Record<string, unknown>): Promise<{ execution_id: string }> {
  const res = await apiClient.post<{ execution_id: string }>('/executions/trigger', {
    workflow_slug: workflowSlug,
    input_data: data,
  });
  return res.data;
}

export async function fetchExecutionDetail(executionId: string): Promise<ExecutionDetail> {
  const resp = await apiClient.get<ExecutionDetail>(`/executions/${executionId}`);
  return resp.data;
}

export async function listExecutions(params?: {
  workflow_slug?: string;
  status?: string;
  page?: number;
  per_page?: number;
}): Promise<ExecutionsListResponse> {
  const res = await apiClient.get<ExecutionsListResponse>('/executions', {
    params: {
      workflow_slug: params?.workflow_slug,
      status: params?.status,
      page: params?.page,
      per_page: params?.per_page,
    },
  });
  return res.data;
}
