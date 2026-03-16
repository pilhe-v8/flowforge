import { VariableInfo } from '../../types';
import { groupBy } from '../../utils/variableResolver';

interface Props {
  value: string;
  variables: VariableInfo[];
  onChange: (val: string) => void;
  placeholder?: string;
}

export function VariableSelector({ value, variables, onChange, placeholder }: Props) {
  const grouped = groupBy(variables, 'stepName');
  return (
    <select
      className="w-full border rounded px-2 py-1 text-sm"
      value={value || ''}
      onChange={e => onChange(e.target.value)}
    >
      <option value="">{placeholder ?? 'Select variable...'}</option>
      {Object.entries(grouped).map(([stepName, vars]) => (
        <optgroup key={stepName} label={stepName}>
          {vars.map(v => (
            <option key={v.fullRef} value={v.fullRef}>
              {v.variableName}{v.type ? ` (${v.type})` : ''}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
