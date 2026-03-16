import { GateRule, VariableInfo } from '../../types';

interface TargetNode { id: string; label: string }

interface Props {
  rules: GateRule[];
  onUpdate: (rules: GateRule[]) => void;
  availableVars: VariableInfo[];
  availableTargets: TargetNode[];
}

const OPERATORS = ['==', '!=', '<', '>', '<=', '>=', 'contains', 'starts_with', 'is_empty'];

export function ConditionBuilder({ rules, onUpdate, availableVars, availableTargets }: Props) {
  const addRule = () => onUpdate([...rules, { if: '', then: '', label: '' }]);
  const updateRule = (i: number, patch: Partial<GateRule>) => {
    const updated = rules.map((r, idx) => idx === i ? { ...r, ...patch } : r);
    onUpdate(updated);
  };
  const removeRule = (i: number) => onUpdate(rules.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-3">
      {rules.map((rule, i) => (
        <div key={i} className="border rounded p-2 space-y-2 bg-gray-50">
          <div className="flex gap-2 items-center">
            <select className="border rounded px-1 py-1 text-sm flex-1"
              value={rule.if.split(' ')[0] || ''}
              onChange={e => updateRule(i, { if: `${e.target.value} ${rule.if.split(' ').slice(1).join(' ')}` })}>
              <option value="">Variable...</option>
              {availableVars.map(v => <option key={v.fullRef} value={v.variableName}>{v.variableName}</option>)}
            </select>
            <select className="border rounded px-1 py-1 text-sm"
              value={rule.if.split(' ')[1] || '=='}
              onChange={e => updateRule(i, { if: `${rule.if.split(' ')[0]} ${e.target.value} ${rule.if.split(' ').slice(2).join(' ')}` })}>
              {OPERATORS.map(op => <option key={op} value={op}>{op}</option>)}
            </select>
            <input className="border rounded px-1 py-1 text-sm flex-1" placeholder="value"
              value={rule.if.split(' ').slice(2).join(' ') || ''}
              onChange={e => updateRule(i, { if: `${rule.if.split(' ').slice(0, 2).join(' ')} ${e.target.value}` })} />
            <button onClick={() => removeRule(i)} className="text-red-500 text-xs">✕</button>
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-xs text-gray-500">then go to</span>
            <select className="border rounded px-1 py-1 text-sm flex-1"
              value={rule.then}
              onChange={e => updateRule(i, { then: e.target.value })}>
              <option value="">Select target...</option>
              {availableTargets.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          </div>
          <input className="border rounded px-1 py-1 text-sm w-full" placeholder="Label (e.g., VIP escalation)"
            value={rule.label || ''}
            onChange={e => updateRule(i, { label: e.target.value })} />
        </div>
      ))}
      <button onClick={addRule} className="text-blue-500 text-sm hover:underline">+ Add Rule</button>
    </div>
  );
}
