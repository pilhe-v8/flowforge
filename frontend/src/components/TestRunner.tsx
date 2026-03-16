import { useState, useRef, useEffect } from 'react';
import { useWorkflowStore } from '../stores/workflowStore';
import { triggerExecution } from '../api/executions';

interface StepResult {
  stepId: string;
  status: string;
  output: Record<string, unknown>;
}

interface Props {
  onHighlight: (stepIds: string[]) => void;
}

export function TestRunner({ onHighlight }: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('{}');
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<StepResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const meta = useWorkflowStore(s => s.meta);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const handleRun = async () => {
    setError(null);
    setSteps([]);
    setRunning(true);
    try {
      const data = JSON.parse(input) as Record<string, unknown>;
      const { execution_id } = await triggerExecution(meta.slug, data);

      // Open WebSocket
      const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/executions/${execution_id}`);
      wsRef.current = ws;

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as {
            step_id?: string;
            status?: string;
            output?: Record<string, unknown>;
            type?: string;
          };
          if (msg.step_id) {
            const result: StepResult = {
              stepId: msg.step_id,
              status: msg.status ?? 'running',
              output: msg.output ?? {},
            };
            setSteps(prev => {
              const existing = prev.findIndex(s => s.stepId === msg.step_id);
              if (existing >= 0) {
                const updated = [...prev];
                updated[existing] = result;
                return updated;
              }
              return [...prev, result];
            });
            // Highlight running nodes
            setSteps(prev => {
              const runningIds = prev.filter(s => s.status === 'running').map(s => s.stepId);
              onHighlight(runningIds);
              return prev;
            });
          }
          if (msg.type === 'done' || msg.status === 'completed' || msg.status === 'failed') {
            setRunning(false);
            ws.close();
            onHighlight([]);
          }
        } catch {
          // ignore parse errors
        }
      };
      ws.onerror = () => {
        setError('WebSocket connection failed');
        setRunning(false);
        onHighlight([]);
      };
      ws.onclose = () => {
        setRunning(false);
        onHighlight([]);
      };
    } catch (e) {
      setError(String(e));
      setRunning(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-3 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600"
      >
        🧪 Test
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-[560px] max-h-[80vh] flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-lg">Test Workflow: {meta.name}</h2>
          <button
            onClick={() => { setOpen(false); wsRef.current?.close(); }}
            className="text-gray-400 hover:text-gray-600 text-xl"
          >
            ✕
          </button>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Trigger Input (JSON)</label>
          <textarea
            className="w-full border rounded p-2 text-sm font-mono h-32 resize-none"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder='{"sender": "user@example.com", "body": "Help!"}'
          />
        </div>

        {error && (
          <div className="text-red-600 text-sm bg-red-50 rounded p-2">{error}</div>
        )}

        <button
          onClick={() => { void handleRun(); }}
          disabled={running}
          className="px-4 py-2 bg-purple-500 text-white rounded text-sm disabled:opacity-50 hover:bg-purple-600"
        >
          {running ? '⏳ Running...' : '▶ Run'}
        </button>

        {steps.length > 0 && (
          <div className="overflow-y-auto flex-1 border rounded p-2 space-y-2">
            <h3 className="text-sm font-medium text-gray-700">Steps</h3>
            {steps.map(s => (
              <div
                key={s.stepId}
                className={`text-xs p-2 rounded ${
                  s.status === 'completed'
                    ? 'bg-green-50'
                    : s.status === 'failed'
                    ? 'bg-red-50'
                    : 'bg-yellow-50'
                }`}
              >
                <div className="font-medium">{s.stepId} — {s.status}</div>
                {Object.keys(s.output).length > 0 && (
                  <pre className="mt-1 text-gray-600 overflow-auto">
                    {JSON.stringify(s.output, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
