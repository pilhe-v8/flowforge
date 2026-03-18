import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { listWorkflows } from '../api/workflows';
import type { WorkflowListItem } from '../types';

type LoadState =
  | { status: 'idle' | 'loading' }
  | { status: 'loaded' }
  | { status: 'error'; message: string };

function statusBadgeClasses(status: string) {
  switch (status) {
    case 'active':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
    case 'draft':
      return 'bg-amber-50 text-amber-800 ring-amber-600/20';
    case 'archived':
    case 'inactive':
      return 'bg-slate-100 text-slate-700 ring-slate-600/20';
    default:
      return 'bg-slate-50 text-slate-700 ring-slate-600/20';
  }
}

export function WorkflowsListPage() {
  const [items, setItems] = useState<WorkflowListItem[]>([]);
  const [state, setState] = useState<LoadState>({ status: 'idle' });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setState({ status: 'loading' });
      try {
        const res = await listWorkflows({ page: 1, per_page: 50 });
        if (cancelled) return;
        setItems(res.workflows);
        setState({ status: 'loaded' });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load workflows';
        if (cancelled) return;
        setState({ status: 'error', message });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const content = useMemo(() => {
    if (state.status === 'loading' || state.status === 'idle') {
      return <div className="text-sm text-slate-600">Loading workflows...</div>;
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
          <div className="text-sm font-medium text-slate-900">No workflows found</div>
          <div className="mt-1 text-sm text-slate-600">Create one in the API, then refresh.</div>
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
                Name
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
              >
                Slug
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
                Version
              </th>
              <th scope="col" className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map(wf => (
              <tr key={wf.slug} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">{wf.name}</td>
                <td className="px-4 py-3 text-sm text-slate-700">
                  <span className="font-mono text-[13px]">{wf.slug}</span>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${statusBadgeClasses(
                      wf.status,
                    )}`}
                  >
                    {wf.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{wf.version}</td>
                <td className="px-4 py-3 text-right text-sm">
                  <Link
                    to={`/workflows/${wf.slug}`}
                    className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                  >
                    Open
                  </Link>
                </td>
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
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Workflows</h1>
            <p className="mt-1 text-sm text-slate-600">Browse and open workflow definitions.</p>
          </div>
        </div>

        <div className="mt-6">{content}</div>
      </div>
    </div>
  );
}
