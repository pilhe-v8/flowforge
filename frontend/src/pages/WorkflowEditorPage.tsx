import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import App from '../App';
import { useWorkflowStore } from '../stores/workflowStore';

type LoadState =
  | { status: 'idle' | 'loading' }
  | { status: 'loaded' }
  | { status: 'error'; message: string };

export function WorkflowEditorPage() {
  const { slug } = useParams();
  const loadWorkflow = useWorkflowStore(s => s.loadWorkflow);

  const [state, setState] = useState<LoadState>({ status: 'idle' });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!slug) {
        setState({ status: 'error', message: 'Missing workflow slug.' });
        return;
      }

      setState({ status: 'loading' });
      try {
        await loadWorkflow(slug);
        if (cancelled) return;
        setState({ status: 'loaded' });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load workflow.';
        if (cancelled) return;
        setState({ status: 'error', message });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [slug, loadWorkflow]);

  if (state.status === 'error') {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-3xl px-4 py-10">
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {state.message}
          </div>
        </div>
      </div>
    );
  }

  // Keep rendering editor while loading to minimize UI churn.
  // The store will update nodes/edges/meta as soon as the fetch completes.
  return <App />;
}
