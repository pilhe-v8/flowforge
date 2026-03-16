import { useWorkflowStore } from '../../stores/workflowStore';

export function ValidationBar() {
  const errors = useWorkflowStore(s => s.errors);
  const errorCount = errors.filter(e => e.severity === 'error').length;
  const warnCount = errors.filter(e => e.severity === 'warning').length;

  if (errors.length === 0) {
    return (
      <div className="h-8 bg-green-50 border-t border-green-200 flex items-center px-4 flex-shrink-0">
        <span className="text-green-600 text-xs">✅ All checks passed</span>
      </div>
    );
  }

  return (
    <div className="bg-red-50 border-t border-red-200 px-4 py-2 flex-shrink-0">
      <div className="flex items-center gap-3 mb-1">
        {errorCount > 0 && (
          <span className="text-red-600 text-xs font-medium">
            ❌ {errorCount} error{errorCount !== 1 ? 's' : ''}
          </span>
        )}
        {warnCount > 0 && (
          <span className="text-yellow-600 text-xs font-medium">
            ⚠️ {warnCount} warning{warnCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        {errors.slice(0, 3).map((e, i) => (
          <span
            key={i}
            className={`text-xs ${e.severity === 'error' ? 'text-red-600' : 'text-yellow-600'}`}
          >
            {e.message}
          </span>
        ))}
        {errors.length > 3 && (
          <span className="text-xs text-gray-500">+{errors.length - 3} more</span>
        )}
      </div>
    </div>
  );
}
