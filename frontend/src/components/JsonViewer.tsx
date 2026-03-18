import { useEffect, useMemo, useRef, useState } from 'react';

type PathSegment = string | number;

export interface JsonViewerProps {
  value: unknown;
  defaultExpandDepth?: number;
  title?: string;
}

const IDENTIFIER_RE = /^[A-Za-z_$][A-Za-z0-9_$]*$/;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value == null || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function isExpandable(value: unknown): value is Record<string, unknown> | unknown[] {
  if (Array.isArray(value)) return true;
  if (isPlainObject(value)) return true;
  return false;
}

function pathToString(path: PathSegment[]): string {
  let out = '$';
  for (const seg of path) {
    if (typeof seg === 'number') {
      out += `[${seg}]`;
      continue;
    }

    if (IDENTIFIER_RE.test(seg)) {
      out += `.${seg}`;
      continue;
    }

    out += `[${JSON.stringify(seg)}]`;
  }
  return out;
}

function nodeIdForPath(path: PathSegment[]): string {
  // Internal stable id encoding; must not collide with any display path.
  return `p:${JSON.stringify(path)}`;
}

function domIdForNodeId(nodeId: string): string {
  // Stable small-ish id for aria-controls.
  let hash = 2166136261;
  for (let i = 0; i < nodeId.length; i++) {
    hash ^= nodeId.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `jsonv-${(hash >>> 0).toString(16)}`;
}

function describeValue(value: unknown): { kind: 'primitive' | 'collection'; text: string } {
  if (value === null) return { kind: 'primitive', text: 'null' };
  if (value === undefined) return { kind: 'primitive', text: 'undefined' };

  const t = typeof value;
  if (t === 'string') return { kind: 'primitive', text: JSON.stringify(value) };
  if (t === 'number') return { kind: 'primitive', text: String(value) };
  if (t === 'boolean') return { kind: 'primitive', text: value ? 'true' : 'false' };
  if (t === 'bigint') return { kind: 'primitive', text: `${String(value)}n` };
  if (t === 'symbol') return { kind: 'primitive', text: String(value) };
  if (t === 'function') return { kind: 'primitive', text: '[Function]' };

  if (value instanceof Date) {
    return { kind: 'primitive', text: JSON.stringify(value.toISOString()) };
  }
  if (value instanceof RegExp) {
    return { kind: 'primitive', text: String(value) };
  }

  if (Array.isArray(value)) {
    return { kind: 'collection', text: `Array(${value.length})` };
  }
  if (isPlainObject(value)) {
    return { kind: 'collection', text: `Object{${Object.keys(value).length}}` };
  }

  // Non-plain objects (Map/Set/class instances) are displayed as a leaf to avoid surprising traversal.
  const name = (value as { constructor?: { name?: string } }).constructor?.name;
  return { kind: 'primitive', text: name ? `[${name}]` : '[Object]' };
}

function safeStringify(value: unknown, pretty: boolean): string {
  if (value === undefined) return 'undefined';
  if (typeof value === 'function') return '[Function]';
  if (typeof value === 'symbol') return String(value);
  if (typeof value === 'bigint') return `${String(value)}n`;

  try {
    const s = JSON.stringify(value, null, pretty ? 2 : 0);
    if (s !== undefined) return s;
  } catch {
    // ignore
  }

  try {
    return String(value);
  } catch {
    return '[Unserializable]';
  }
}

function jsonStringifyPretty(value: unknown): string {
  try {
    const s = JSON.stringify(value, null, 2);
    if (s !== undefined) return s;
  } catch {
    // ignore
  }
  return safeStringify(value, true);
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through
  }

  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', 'true');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

function computeInitialExpanded(value: unknown, defaultExpandDepth: number): Set<string> {
  const expanded = new Set<string>();
  const seen = new WeakSet<object>();

  function walk(node: unknown, path: PathSegment[], depth: number) {
    if (!isExpandable(node)) return;
    if (node && typeof node === 'object') {
      if (seen.has(node)) return;
      seen.add(node);
    }

    if (depth < defaultExpandDepth) {
      expanded.add(nodeIdForPath(path));
    } else {
      return;
    }

    if (Array.isArray(node)) {
      for (let i = 0; i < node.length; i++) {
        walk(node[i], [...path, i], depth + 1);
      }
      return;
    }

    for (const key of Object.keys(node)) {
      walk((node as Record<string, unknown>)[key], [...path, key], depth + 1);
    }
  }

  walk(value, [], 0);
  return expanded;
}

function computeExpandedAll(value: unknown): Set<string> {
  const expanded = new Set<string>();
  const seen = new WeakSet<object>();

  function walk(node: unknown, path: PathSegment[]) {
    if (!isExpandable(node)) return;
    if (node && typeof node === 'object') {
      if (seen.has(node)) return;
      seen.add(node);
    }

    expanded.add(nodeIdForPath(path));

    if (Array.isArray(node)) {
      for (let i = 0; i < node.length; i++) {
        walk(node[i], [...path, i]);
      }
      return;
    }

    for (const key of Object.keys(node)) {
      walk((node as Record<string, unknown>)[key], [...path, key]);
    }
  }

  walk(value, []);
  return expanded;
}

function KeyLabel({ seg }: { seg: PathSegment }) {
  if (typeof seg === 'number') {
    return <span className="text-slate-500">[{seg}]</span>;
  }
  if (IDENTIFIER_RE.test(seg)) {
    return <span className="text-slate-700">{seg}</span>;
  }
  return <span className="text-slate-700">[{JSON.stringify(seg)}]</span>;
}

function truncate(s: string, max: number) {
  if (s.length <= max) return s;
  return `${s.slice(0, Math.max(0, max - 3))}...`;
}

function cssEscape(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(value);
  // Minimal escape for attribute selectors.
  return value.replace(/["\\]/g, '\\$&');
}

export function JsonViewer({ value, defaultExpandDepth = 2, title }: JsonViewerProps) {
  const clampExpandDepth = (depth: number) => Math.max(0, Math.min(6, depth));
  const [expandDepthUi, setExpandDepthUi] = useState(() => clampExpandDepth(defaultExpandDepth));
  const [appliedExpandDepth, setAppliedExpandDepth] = useState(() =>
    clampExpandDepth(defaultExpandDepth),
  );

  useEffect(() => {
    const next = clampExpandDepth(defaultExpandDepth);
    setExpandDepthUi(next);
    setAppliedExpandDepth(next);
  }, [defaultExpandDepth]);

  const initialExpanded = useMemo(
    () => computeInitialExpanded(value, appliedExpandDepth),
    [value, appliedExpandDepth],
  );
  const [expanded, setExpanded] = useState<Set<string>>(() => initialExpanded);

  const [searchQuery, setSearchQuery] = useState('');
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);
  const [pendingScrollNodeId, setPendingScrollNodeId] = useState<string | null>(null);
  const [flashNodeId, setFlashNodeId] = useState<string | null>(null);
  const flashTimerRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setExpanded(initialExpanded);
  }, [initialExpanded]);

  useEffect(() => {
    return () => {
      if (flashTimerRef.current != null) {
        window.clearTimeout(flashTimerRef.current);
        flashTimerRef.current = null;
      }
    };
  }, []);

  const handleCopy = async (text: string) => {
    await copyToClipboard(text);
  };

  const headerTitle = title ?? 'JSON';

  type FlatNode = {
    path: PathSegment[];
    nodeId: string;
    pathStr: string;
    renderedValue: string;
  };

  const flattenedNodes: FlatNode[] = useMemo(() => {
    const out: FlatNode[] = [];

    function walk(nodeValue: unknown, path: PathSegment[], ancestors: object[]) {
      const id = nodeIdForPath(path);
      const circular =
        nodeValue != null && typeof nodeValue === 'object' && ancestors.includes(nodeValue as object);

      const desc = circular
        ? { kind: 'primitive' as const, text: '[Circular]' }
        : describeValue(nodeValue);

      out.push({
        path,
        nodeId: id,
        pathStr: pathToString(path),
        renderedValue: desc.text,
      });

      if (circular) return;
      if (!isExpandable(nodeValue)) return;

      const nextAncestors =
        nodeValue != null && typeof nodeValue === 'object'
          ? [...ancestors, nodeValue as object]
          : ancestors;

      if (Array.isArray(nodeValue)) {
        for (let i = 0; i < nodeValue.length; i++) {
          walk(nodeValue[i], [...path, i], nextAncestors);
        }
        return;
      }

      for (const key of Object.keys(nodeValue)) {
        walk((nodeValue as Record<string, unknown>)[key], [...path, key], nextAncestors);
      }
    }

    walk(value, [], []);
    return out;
  }, [value]);

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const matches: FlatNode[] = useMemo(() => {
    if (!normalizedQuery) return [];

    return flattenedNodes.filter(n => {
      const haystack = `${n.pathStr} ${n.renderedValue}`.toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [flattenedNodes, normalizedQuery]);

  useEffect(() => {
    setActiveMatchIndex(0);
    setPendingScrollNodeId(null);
    setFlashNodeId(null);
  }, [normalizedQuery]);

  useEffect(() => {
    if (matches.length === 0) {
      if (activeMatchIndex !== 0) setActiveMatchIndex(0);
      return;
    }
    if (activeMatchIndex >= matches.length) setActiveMatchIndex(0);
  }, [matches.length, activeMatchIndex]);

  const goToMatch = (nextIndex: number) => {
    const total = matches.length;
    if (total === 0) return;

    const idx = ((nextIndex % total) + total) % total;
    const match = matches[idx];
    setActiveMatchIndex(idx);

    const ancestorIds: string[] = [];
    for (let i = 0; i < match.path.length; i++) {
      ancestorIds.push(nodeIdForPath(match.path.slice(0, i)));
    }
    if (match.path.length === 0) ancestorIds.push(nodeIdForPath([]));

    setExpanded(prev => {
      const next = new Set(prev);
      for (const aid of ancestorIds) next.add(aid);
      return next;
    });

    setPendingScrollNodeId(match.nodeId);
  };

  useEffect(() => {
    if (!pendingScrollNodeId) return;

    let cancelled = false;
    let attempts = 0;
    const targetNodeId = pendingScrollNodeId;

    const tryScroll = () => {
      if (cancelled) return;

      const selector = `[data-nodeid="${cssEscape(targetNodeId)}"]`;
      const row = containerRef.current?.querySelector(selector) as HTMLElement | null;
      if (row) {
        row.scrollIntoView({ block: 'nearest' });

        setFlashNodeId(targetNodeId);
        setPendingScrollNodeId(null);

        if (flashTimerRef.current != null) {
          window.clearTimeout(flashTimerRef.current);
        }
        flashTimerRef.current = window.setTimeout(() => {
          setFlashNodeId(current => (current === targetNodeId ? null : current));
          flashTimerRef.current = null;
        }, 1400);
        return;
      }

      attempts++;
      if (attempts <= 8) {
        window.requestAnimationFrame(tryScroll);
      } else {
        setPendingScrollNodeId(null);
      }
    };

    window.requestAnimationFrame(tryScroll);
    return () => {
      cancelled = true;
    };
  }, [pendingScrollNodeId, expanded]);

  const Node = ({
    nodeValue,
    path,
    depth,
    label,
    ancestors,
  }: {
    nodeValue: unknown;
    path: PathSegment[];
    depth: number;
    label: PathSegment | null;
    ancestors: object[];
  }) => {
    const id = nodeIdForPath(path);
    const childrenDomId = domIdForNodeId(id);

    const circular =
      nodeValue != null &&
      typeof nodeValue === 'object' &&
      ancestors.includes(nodeValue as object);

    const expandable = !circular && isExpandable(nodeValue);
    const isOpen = expandable ? expanded.has(id) : false;

    const desc = circular
      ? { kind: 'primitive' as const, text: '[Circular]' }
      : describeValue(nodeValue);
    const pathStr = pathToString(path);

    const toggle = () => {
      if (!expandable) return;
      setExpanded(prev => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    };

    const rowIndent = depth * 14;
    const showActions = path.length > 0;
    const isFlash = flashNodeId === id;

    return (
      <div>
        <div
          data-nodeid={id}
          className={
            isFlash
              ? 'flex items-start gap-2 bg-slate-100 py-1 ring-1 ring-inset ring-slate-300 hover:bg-slate-100'
              : 'flex items-start gap-2 py-1 hover:bg-slate-50'
          }
          style={{ paddingLeft: rowIndent }}
        >
          <button
            type="button"
            onClick={toggle}
            disabled={!expandable}
            className={
              expandable
                ? 'mt-0.5 w-4 shrink-0 rounded text-[10px] leading-4 text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1 focus-visible:ring-offset-white'
                : 'mt-0.5 w-4 shrink-0 text-[10px] leading-4 text-slate-300'
            }
            aria-label={expandable ? (isOpen ? 'Collapse' : 'Expand') : 'Leaf'}
            aria-expanded={expandable ? isOpen : undefined}
            aria-controls={expandable ? childrenDomId : undefined}
          >
            {expandable ? (isOpen ? 'v' : '>') : ''}
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0 font-mono text-xs">
                {label != null && (
                  <>
                    <KeyLabel seg={label} />
                    <span className="text-slate-400">: </span>
                  </>
                )}

                {desc.kind === 'collection' ? (
                  <span className="text-slate-600">{desc.text}</span>
                ) : (
                  <span className="text-slate-900">{truncate(desc.text, 160)}</span>
                )}
              </div>

              <div className="shrink-0">
                <div className="flex items-center gap-2 text-[11px]">
                  {showActions && (
                    <button
                      type="button"
                      onClick={() => void handleCopy(pathStr)}
                      className="rounded px-2 py-0.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                      title={pathStr}
                    >
                      Copy path
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => void handleCopy(jsonStringifyPretty(nodeValue))}
                    className="rounded px-2 py-0.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                  >
                    Copy value
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {expandable && isOpen && (
          <div id={childrenDomId}>
            {Array.isArray(nodeValue)
              ? nodeValue.map((child, idx) => (
                  <Node
                    key={nodeIdForPath([...path, idx])}
                    nodeValue={child}
                    path={[...path, idx]}
                    depth={depth + 1}
                    label={idx}
                    ancestors={
                      nodeValue != null && typeof nodeValue === 'object'
                        ? [...ancestors, nodeValue as object]
                        : ancestors
                    }
                  />
                ))
              : Object.keys(nodeValue).map(k => (
                  <Node
                    key={nodeIdForPath([...path, k])}
                    nodeValue={(nodeValue as Record<string, unknown>)[k]}
                    path={[...path, k]}
                    depth={depth + 1}
                    label={k}
                    ancestors={
                      nodeValue != null && typeof nodeValue === 'object'
                        ? [...ancestors, nodeValue as object]
                        : ancestors
                    }
                  />
                ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">{headerTitle}</div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-2 py-1">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium text-slate-600">Depth</span>
              <select
                value={expandDepthUi}
                onChange={e => setExpandDepthUi(clampExpandDepth(Number(e.target.value)))}
                className="h-6 rounded border border-slate-200 bg-white px-1.5 text-xs text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                aria-label="Expand depth"
              >
                {Array.from({ length: 7 }, (_, i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setAppliedExpandDepth(expandDepthUi)}
                className="rounded px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
              >
                Apply
              </button>
            </div>

            <div className="h-4 w-px bg-slate-200" />

            <button
              type="button"
              onClick={() => setExpanded(computeExpandedAll(value))}
              className="rounded px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              Expand all
            </button>
            <button
              type="button"
              onClick={() => setExpanded(new Set())}
              className="rounded px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              Collapse all
            </button>
          </div>

          <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-2 py-1">
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  goToMatch(activeMatchIndex + (e.shiftKey ? -1 : 1));
                }
              }}
              placeholder="Search"
              className="w-40 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus-visible:outline-none"
              aria-label="Search JSON"
            />

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => goToMatch(activeMatchIndex - 1)}
                disabled={matches.length === 0}
                className={
                  matches.length === 0
                    ? 'rounded px-1.5 py-0.5 text-[11px] text-slate-300'
                    : 'rounded px-1.5 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white'
                }
                aria-label="Previous match"
              >
                Prev
              </button>
              <button
                type="button"
                onClick={() => goToMatch(activeMatchIndex + 1)}
                disabled={matches.length === 0}
                className={
                  matches.length === 0
                    ? 'rounded px-1.5 py-0.5 text-[11px] text-slate-300'
                    : 'rounded px-1.5 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white'
                }
                aria-label="Next match"
              >
                Next
              </button>

              <div className="min-w-[52px] text-right text-[11px] tabular-nums text-slate-500">
                {matches.length === 0 ? '0 / 0' : `${activeMatchIndex + 1} / ${matches.length}`}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => void handleCopy(jsonStringifyPretty(value))}
            className="shrink-0 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
          >
            Copy JSON
          </button>
        </div>
      </div>

      <div ref={containerRef} className="max-h-[520px] overflow-auto px-1 py-1">
        <Node nodeValue={value} path={[]} depth={0} label={null} ancestors={[]} />
      </div>
    </div>
  );
}
