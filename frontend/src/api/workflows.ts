import { apiClient } from './client';
import { WorkflowVersion, WorkflowsListResponse } from '../types';

export async function fetchWorkflow(slug: string): Promise<WorkflowVersion> {
  const res = await apiClient.get<WorkflowVersion>(`/workflows/${slug}`);
  return res.data;
}

export async function saveWorkflow(slug: string, yamlDefinition: string): Promise<void> {
  await apiClient.put(`/workflows/${slug}`, { yaml_definition: yamlDefinition });
}

export async function deployWorkflow(slug: string): Promise<void> {
  await apiClient.post(`/workflows/${slug}/deploy`);
}

export async function listWorkflowVersions(slug: string): Promise<WorkflowVersion[]> {
  const res = await apiClient.get<{ versions: WorkflowVersion[] }>(`/workflows/${slug}/versions`);
  return res.data.versions;
}

export async function listWorkflows(params?: {
  page?: number;
  per_page?: number;
  search?: string;
}): Promise<WorkflowsListResponse> {
  const res = await apiClient.get<WorkflowsListResponse>('/workflows', {
    params: {
      page: params?.page,
      per_page: params?.per_page,
      search: params?.search,
    },
  });
  return res.data;
}
