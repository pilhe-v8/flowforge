import { useState } from 'react';
import { NODE_DEFINITIONS } from './NodeDefinitions';

interface Props {
  nodeType: string;
}

export function DefinitionDrawer({ nodeType }: Props) {
  const [open, setOpen] = useState(false);
  const def = NODE_DEFINITIONS[nodeType];
  if (!def) return null;

  return (
    <div className="border-t border-gray-200">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-50"
      >
        <span>? What is a {def.title}?</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2">
          <p className="text-xs text-gray-600">{def.summary}</p>
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="text-left text-gray-400">
                <th className="pb-1 font-medium">Field</th>
                <th className="pb-1 font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {def.fields.map(field => (
                <tr key={field.name} className="border-t border-gray-100">
                  <td className="py-1 pr-2 font-mono text-blue-700 whitespace-nowrap">
                    {field.name}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </td>
                  <td className="py-1 text-gray-600">
                    <div>{field.description}</div>
                    <div className="text-gray-400 font-mono">{field.example}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
