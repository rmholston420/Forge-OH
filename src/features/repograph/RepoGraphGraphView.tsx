'use client';

/**
 * src/features/repograph/RepoGraphGraphView.tsx
 *
 * Stage 4.2/4.3 — force-directed 2D graph view of the top-N PageRank
 * symbols plus their containing files, connected by CONTAINS and CALLS
 * edges.
 *
 * Ships as a dynamic import to keep the canvas / d3 bundles out of the
 * SSR pass (react-force-graph-2d is browser-only).
 *
 * Interaction model:
 *   - Node size scales with PageRank (log-normalized) for symbols and a
 *     constant midpoint for files.
 *   - Node color encodes {kind, category}.
 *   - Clicking a symbol node emits onSelectSymbol({rel_path, name,
 *     start_line}); the enclosing panel wires that to the existing
 *     useCallers/useCallees hooks so the drill-down side panel updates
 *     without a round-trip.
 */
import React, { useMemo, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { RepoGraphFullGraph, RepoGraphNode } from '@/lib/schemas/repograph';

// SSR guard: react-force-graph-2d touches window/canvas at import time.
const ForceGraph2D = dynamic(
  () => import('react-force-graph-2d').then((mod) => mod.default),
  { ssr: false },
);

export interface SelectedSymbol {
  rel_path: string;
  name: string;
  start_line: number;
}

export interface RepoGraphGraphViewProps {
  graph: RepoGraphFullGraph;
  height?: number;
  onSelectSymbol?: (sym: SelectedSymbol) => void;
}

// Rough color palette that survives light + dark backgrounds.
const NODE_COLORS: Record<string, string> = {
  'file:':          '#8892b0',
  'symbol:function':'#64ffda',
  'symbol:method':  '#5ac8fa',
  'symbol:class':   '#ffab70',
  'symbol:default': '#c9d1d9',
};

function nodeColor(n: RepoGraphNode): string {
  if (n.kind === 'file') return NODE_COLORS['file:'];
  const key = `symbol:${n.category ?? 'default'}`;
  return NODE_COLORS[key] ?? NODE_COLORS['symbol:default'];
}

// Log-normalize PageRank into a 2..12 radius band. Files use a
// constant mid-band value so they stay legible without dominating.
function nodeRadius(n: RepoGraphNode): number {
  if (n.kind === 'file') return 6;
  const pr = Math.max(1e-6, n.pagerank ?? 0);
  const scaled = Math.log10(1 + pr * 1000);
  return Math.min(12, Math.max(2, 2 + scaled * 4));
}

export const RepoGraphGraphView: React.FC<RepoGraphGraphViewProps> = ({
  graph,
  height = 520,
  onSelectSymbol,
}) => {
  // The lib mutates node.x/y in place; cloning once decouples our schema
  // from render-time state.
  const data = useMemo(
    () => ({
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.links.map((l) => ({ ...l })),
    }),
    [graph],
  );

  const fgRef = useRef<unknown>(null);

  const handleNodeClick = useCallback(
    (node: unknown) => {
      const n = node as RepoGraphNode;
      if (n.kind !== 'symbol' || !onSelectSymbol) return;
      if (n.start_line == null) return;
      onSelectSymbol({
        rel_path: n.rel_path,
        name: n.label,
        start_line: n.start_line,
      });
    },
    [onSelectSymbol],
  );

  const paintNode = useCallback(
    (node: unknown, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as RepoGraphNode & { x?: number; y?: number };
      const r = nodeRadius(n);
      const x = n.x ?? 0;
      const y = n.y ?? 0;

      // circle
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = nodeColor(n);
      ctx.fill();

      // label (only at high zoom or for prominent nodes)
      const fontSize = 10 / globalScale;
      const wantsLabel =
        globalScale > 1.5 || (n.kind === 'symbol' && (n.pagerank ?? 0) > 0.01);
      if (wantsLabel) {
        ctx.font = `${fontSize}px sans-serif`;
        ctx.fillStyle = '#e6edf3';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(n.label, x, y + r + 1);
      }
    },
    [],
  );

  return (
    <div
      data-testid="repograph-graph-view"
      style={{ width: '100%', height, position: 'relative' }}
    >
      <ForceGraph2D
        ref={fgRef as never}
        graphData={data as never}
        nodeId="id"
        nodeLabel={((n: unknown) => {
          const nn = n as RepoGraphNode;
          if (nn.kind === 'file') return nn.rel_path;
          return `${nn.rel_path}\n${nn.label}${
            nn.start_line != null ? ` :${nn.start_line}` : ''
          }`;
        }) as never}
        linkColor={((l: unknown) => {
          const t = (l as { type: string }).type;
          return t === 'CALLS' ? '#f778ba' : '#3d4451';
        }) as never}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={0.6}
        cooldownTime={2500}
        nodeCanvasObject={paintNode as never}
        onNodeClick={handleNodeClick as never}
        height={height}
      />
    </div>
  );
};

export default RepoGraphGraphView;
