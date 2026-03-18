import { Fragment, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchExecutionDetail } from '../api/executions';
import { JsonViewer } from '../components/JsonViewer';
import type { ExecutionDetail, ExecutionStep } from '../types';

type LoadState =
  | { status: 'idle' | 'loading' }
  | { status: 'loaded' }
  | { status: 'error'; message: string };

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

function formatInt(n: number | null | undefined) {
  if (n == null) return '-';
  return new Intl.NumberFormat('en-US').format(n);
}

function formatUsd(value: number | null | undefined) {
  if (value == null) return '-';
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: value < 1 ? 4 : 2,
    }).format(value);
  } catch {
    return `$${value.toFixed(4)}`;
  }
}

function stepLabel(step: ExecutionStep) {
  const name = step.step_name?.trim();
  if (name) return name;
  return step.step_id;
}

export function ExecutionDetailPage() {
  const { executionId } = useParams();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [state, setState] = useState<LoadState>({ status: 'idle' });
  const [expandedStepIds, setExpandedStepIds] = useState<Set<string>>(() => new Set());

  const errorMessage = state.status === 'error' ? state.message : null;

  useEffect(() => {
    if (!executionId) return;
    const id = executionId;

    let cancelled = false;
    async function load() {
      setState({ status: 'loading' });
      try {
        const res = await fetchExecutionDetail(id);
        if (cancelled) return;
        setDetail(res);
        setState({ status: 'loaded' });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load execution';
        if (cancelled) return;
        setState({ status: 'error', message });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [executionId]);

  const header = useMemo(() => {
    if (!executionId) {
      return (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Missing execution id
        </div>
      );
    }

    const workflowSlug = detail?.workflow_slug ?? '-';
    const status = detail?.status ?? 'unknown';
    const totalTokens =
      detail != null ? (detail.total_input_tokens ?? 0) + (detail.total_output_tokens ?? 0) : null;

    return (
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 px-4 py-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-600">
              <Link to="/executions" className="hover:underline">
                Executions
              </Link>
              <span className="text-slate-400"> / </span>
              <span className="font-mono text-[12px] text-slate-700">{executionId}</span>
            </div>
            <h1 className="mt-1 text-xl font-semibold text-slate-900">Execution detail</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <div className="text-slate-600">
                Workflow: <span className="font-medium text-slate-900">{workflowSlug}</span>
              </div>
              <span
                className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${statusBadgeClasses(
                  status,
                )}`}
              >
                {status}
              </span>
            </div>
          </div>

          <div className="w-full shrink-0 md:w-auto">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-[11px] font-medium text-slate-600">Duration</div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">
                  {formatDuration(detail?.duration_ms ?? null)}
                </div>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-[11px] font-medium text-slate-600">Tokens</div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">
                  {totalTokens == null ? '-' : formatInt(totalTokens)}
                </div>
                <div className="mt-0.5 text-[11px] text-slate-600">
                  in {formatInt(detail?.total_input_tokens)} / out {formatInt(detail?.total_output_tokens)}
                </div>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-[11px] font-medium text-slate-600">Cost</div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">
                  {formatUsd(detail?.estimated_cost_usd)}
                </div>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-[11px] font-medium text-slate-600">Steps</div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">
                  {detail?.steps ? formatInt(detail.steps.length) : '-'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }, [detail, executionId]);

  const content = useMemo(() => {
    if (!executionId) return null;

    if (state.status === 'idle' || state.status === 'loading') {
      return <div className="text-sm text-slate-600">Loading execution...</div>;
    }

    if (state.status === 'error') {
      return (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorMessage}
        </div>
      );
    }

    if (!detail) {
      return (
        <div className="rounded-md border border-slate-200 bg-white px-4 py-6 text-sm text-slate-700">
          Execution not found.
        </div>
      );
    }

    const toggleExpanded = (stepId: string) => {
      setExpandedStepIds(prev => {
        const next = new Set(prev);
        if (next.has(stepId)) next.delete(stepId);
        else next.add(stepId);
        return next;
      });
    };

    return (
      <div className="space-y-6">
        <section>
          <h2 className="text-sm font-semibold text-slate-900">Input data</h2>
          <div className="mt-2">
            <JsonViewer value={detail.input_data ?? {}} title="Execution input" defaultExpandDepth={2} />
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold text-slate-900">Output data</h2>
          <div className="mt-2">
            <JsonViewer value={detail.output_data ?? {}} title="Execution output" defaultExpandDepth={2} />
          </div>
        </section>

        <section>
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Steps</h2>
              <p className="mt-1 text-sm text-slate-600">Expand any step to inspect input and output.</p>
            </div>
          </div>

          <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                    >
                      Step
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
                      Type
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                    >
                      Model
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                    >
                      Duration
                    </th>
                    <th scope="col" className="px-4 py-3" />
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {detail.steps.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-sm text-slate-600">
                        No steps recorded.
                      </td>
                    </tr>
                  ) : (
                    detail.steps.map(step => {
                      const isOpen = expandedStepIds.has(step.step_id);
                      return (
                        <Fragment key={step.step_id}>
                          <tr className="hover:bg-slate-50/60">
                            <td className="px-4 py-3">
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-slate-900">
                                  {stepLabel(step)}
                                </div>
                                <div className="mt-0.5 font-mono text-[12px] text-slate-500">
                                  {step.step_id}
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              <span
                                className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${statusBadgeClasses(
                                  step.status,
                                )}`}
                              >
                                {step.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-700">{step.type}</td>
                            <td className="px-4 py-3 text-sm text-slate-700">{step.model ?? '-'}</td>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              {formatDuration(step.duration_ms)}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => toggleExpanded(step.step_id)}
                                className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                              >
                                {isOpen ? 'Hide' : 'Show'}
                              </button>
                            </td>
                          </tr>
                          {isOpen && (
                            <tr className="bg-slate-50/40">
                              <td colSpan={6} className="px-4 py-4">
                                <div className="grid gap-4 md:grid-cols-2">
                                  <JsonViewer
                                    value={step.input ?? {}}
                                    title="Step input"
                                    defaultExpandDepth={2}
                                  />
                                  <JsonViewer
                                    value={step.output ?? {}}
                                    title="Step output"
                                    defaultExpandDepth={2}
                                  />
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    );
  }, [detail, executionId, expandedStepIds, errorMessage, state.status]);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8">
        {header}
        <div className="mt-6">{content}</div>
      </div>
    </div>
  );
}
