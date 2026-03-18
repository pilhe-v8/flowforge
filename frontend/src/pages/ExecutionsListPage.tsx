import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { listExecutions } from '../api/executions';
import type { ExecutionListItem } from '../types';

type LoadState =
  | { status: 'idle' | 'loading' }
  | { status: 'loaded' }
  | { status: 'error'; message: string };

type ExecutionStatusFilter = '' | 'queued' | 'running' | 'completed' | 'failed';

function statusBadgeClasses(status: string) {
  switch (status) {
    case 'queued':
      return 'bg-slate-100 text-slate-700 ring-slate-600/20';
    case 'running':
      return 'bg-blue-50 text-blue-700 ring-blue-600/20';
    case 'completed':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
    case 'failed':
      return 'bg-red-50 text-red-700 ring-red-600/20';
    default:
      return 'bg-slate-50 text-slate-700 ring-slate-600/20';
  }
}

function formatDuration(durationMs: number | null) {
  if (durationMs == null) return '-';

  const seconds = durationMs / 1000;
  if (seconds < 1) return `${Math.round(durationMs)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;

  const minutes = Math.floor(seconds / 60);
  const rem = Math.round(seconds % 60);
  return `${minutes}m ${rem}s`;
}

export function ExecutionsListPage() {
  const [items, setItems] = useState<ExecutionListItem[]>([]);
  const [state, setState] = useState<LoadState>({ status: 'idle' });
  const [workflowSlug, setWorkflowSlug] = useState('');
  const [status, setStatus] = useState<ExecutionStatusFilter>('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setState({ status: 'loading' });
      try {
        const res = await listExecutions({
          page: 1,
          per_page: 50,
          workflow_slug: workflowSlug.trim() || undefined,
          status: status || undefined,
        });
        if (cancelled) return;
        setItems(res.executions);
        setState({ status: 'loaded' });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load executions';
        if (cancelled) return;
        setState({ status: 'error', message });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [workflowSlug, status]);

  const content = useMemo(() => {
    if (state.status === 'loading' || state.status === 'idle') {
      return <div className="text-sm text-slate-600">Loading executions...</div>;
    }

    if (state.status === 'error') {
      return (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {state.message}
        </div>
      );
    }

    if (items.length === 0) {
      return (
        <div className="rounded-md border border-slate-200 bg-white px-4 py-8 text-center">
          <div className="text-sm font-medium text-slate-900">No executions found</div>
          <div className="mt-1 text-sm text-slate-600">Try adjusting filters or trigger a workflow.</div>
        </div>
      );
    }

    return (
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Execution ID
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Workflow
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Status
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Queued At
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Duration
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map(ex => (
              <tr key={ex.execution_id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 text-sm text-slate-900">
                  <Link
                    to={`/executions/${ex.execution_id}`}
                    className="font-mono text-[13px] text-slate-900 hover:underline"
                  >
                    {ex.execution_id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{ex.workflow_slug}</td>
                <td className="px-4 py-3 text-sm text-slate-700">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${statusBadgeClasses(
                      ex.status,
                    )}`}
                  >
                    {ex.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{ex.queued_at ?? '-'}</td>
                <td className="px-4 py-3 text-sm text-slate-700">{formatDuration(ex.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }, [items, state]);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Executions</h1>
            <p className="mt-1 text-sm text-slate-600">Browse recent workflow executions.</p>
          </div>

          <div className="flex w-full flex-col gap-3 md:w-auto md:flex-row md:items-center">
            <label className="flex w-full flex-col gap-1 md:w-64">
              <span className="text-xs font-medium text-slate-700">Workflow</span>
              <input
                value={workflowSlug}
                onChange={e => setWorkflowSlug(e.target.value)}
                placeholder="workflow slug"
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none"
              />
            </label>

            <label className="flex w-full flex-col gap-1 md:w-48">
              <span className="text-xs font-medium text-slate-700">Status</span>
              <select
                value={status}
                onChange={e => setStatus(e.target.value as ExecutionStatusFilter)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-900 focus:outline-none"
              >
                <option value="">All</option>
                <option value="queued">queued</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-6">{content}</div>
      </div>
    </div>
  );
}
