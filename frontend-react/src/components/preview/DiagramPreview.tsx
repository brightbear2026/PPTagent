/* ============================================================
   DiagramPreview — SVG 概念图预览
   支持: process_flow / hierarchy / comparison / 通用节点列表
   ============================================================ */

import React from 'react';
import type { ContentDiagramSpec } from '../../types';

interface Props {
  diagram: ContentDiagramSpec;
  width: number;
  height: number;
}

const C = {
  primary: '#003D6E',
  accent:  '#C9A84C',
  muted:   '#8B9DAF',
  bg:      '#EEF4FA',
  border:  '#C8D8E8',
  white:   '#ffffff',
  text:    '#2D3436',
} as const;

const DiagramPreview: React.FC<Props> = ({ diagram, width, height }) => {
  const type = diagram.diagram_type;
  if (type === 'process_flow')  return <ProcessFlow   diagram={diagram} width={width} height={height} />;
  if (type === 'hierarchy')     return <Hierarchy     diagram={diagram} width={width} height={height} />;
  if (type === 'comparison')    return <Comparison    diagram={diagram} width={width} height={height} />;
  if (type === 'architecture')  return <Architecture  diagram={diagram} width={width} height={height} />;
  if (type === 'framework')     return <Framework     diagram={diagram} width={width} height={height} />;
  return <NodeList diagram={diagram} width={width} height={height} />;
};

/* ── Arrow marker defs ── */
const ArrowDefs: React.FC = () => (
  <defs>
    <marker id="dp-arrow" viewBox="0 0 6 6" refX={5} refY={3} markerWidth={4} markerHeight={4} orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill={C.muted} />
    </marker>
  </defs>
);

/* ── truncate helper ── */
function trunc(s: any, n: number) {
  const str = (s == null) ? '' : String(s);
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
}

/* ── process_flow: left-to-right boxes with arrows ── */
const ProcessFlow: React.FC<Props> = ({ diagram, width, height }) => {
  const nodes = (diagram.nodes ?? []).slice(0, 7);
  if (!nodes.length) return <Fallback label={diagram.title} width={width} height={height} />;

  const pad = 8;
  const arrowW = 10;
  const n = nodes.length;
  const totalArrow = (n - 1) * arrowW;
  const boxW = Math.floor((width - 2 * pad - totalArrow) / n);
  const boxH = Math.min(36, height - 32);
  const y = (height - boxH) / 2;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <ArrowDefs />
      {nodes.map((node, i) => {
        const x = pad + i * (boxW + arrowW);
        const isFirst = i === 0;
        const isLast  = i === n - 1;
        const fill = isFirst ? C.primary : isLast ? C.accent : C.bg;
        const textFill = (isFirst || isLast) ? C.white : C.primary;
        return (
          <g key={node.id ?? i}>
            <rect x={x} y={y} width={boxW} height={boxH} rx={3} fill={fill} stroke={C.border} strokeWidth={0.8} />
            <text x={x + boxW / 2} y={y + boxH / 2} textAnchor="middle" dominantBaseline="middle"
              fontSize={8} fill={textFill}>
              {trunc(node.label, 9)}
            </text>
            {i < n - 1 && (
              <line x1={x + boxW} y1={y + boxH / 2} x2={x + boxW + arrowW} y2={y + boxH / 2}
                stroke={C.muted} strokeWidth={1.2} markerEnd="url(#dp-arrow)" />
            )}
          </g>
        );
      })}
      <Footer label={diagram.title} width={width} height={height} />
    </svg>
  );
};

/* ── hierarchy: root → children ── */
const Hierarchy: React.FC<Props> = ({ diagram, width, height }) => {
  const nodes = diagram.nodes ?? [];
  if (!nodes.length) return <Fallback label={diagram.title} width={width} height={height} />;

  const root     = nodes[0];
  const children = nodes.slice(1, 6);
  const rootW = 80, rootH = 26;
  const rootX = (width - rootW) / 2;
  const rootY = 14;
  const rootCX = rootX + rootW / 2;
  const rootCY = rootY + rootH;

  const childH = 22;
  const maxChildW = 56;
  const childW = children.length
    ? Math.min(maxChildW, (width - 16) / children.length - 6)
    : maxChildW;
  const childY = rootY + rootH + 22;
  const totalW = children.length * (childW + 6) - 6;
  const cStartX = (width - totalW) / 2;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {/* Root */}
      <rect x={rootX} y={rootY} width={rootW} height={rootH} rx={3} fill={C.primary} />
      <text x={rootCX} y={rootY + rootH / 2} textAnchor="middle" dominantBaseline="middle"
        fontSize={9} fill={C.white}>
        {trunc(root.label, 10)}
      </text>

      {/* Children */}
      {children.map((node, i) => {
        const cx = cStartX + i * (childW + 6);
        const nodeCX = cx + childW / 2;
        const nodeCY = childY + childH / 2;
        return (
          <g key={node.id ?? i}>
            <line x1={rootCX} y1={rootCY} x2={nodeCX} y2={childY} stroke={C.border} strokeWidth={1} />
            <rect x={cx} y={childY} width={childW} height={childH} rx={3} fill={C.bg} stroke={C.border} strokeWidth={0.8} />
            <text x={nodeCX} y={nodeCY} textAnchor="middle" dominantBaseline="middle"
              fontSize={8} fill={C.primary}>
              {trunc(node.label, 7)}
            </text>
          </g>
        );
      })}
      <Footer label={diagram.title} width={width} height={height} />
    </svg>
  );
};

/* ── comparison: two-column layout ── */
const Comparison: React.FC<Props> = ({ diagram, width, height }) => {
  const nodes = diagram.nodes ?? [];
  const leftLabel  = diagram.x_axis?.low  ?? 'A';
  const rightLabel = diagram.x_axis?.high ?? 'B';

  const half  = Math.ceil(nodes.length / 2);
  const left  = nodes.slice(0, half);
  const right = nodes.slice(half);
  const pad   = 8;
  const colW  = (width - 3 * pad) / 2;
  const headerH = 22;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {/* Left header */}
      <rect x={pad} y={8} width={colW} height={headerH} rx={3} fill={C.primary} />
      <text x={pad + colW / 2} y={8 + headerH / 2} textAnchor="middle" dominantBaseline="middle"
        fontSize={9} fill={C.white}>{trunc(leftLabel, 10)}</text>

      {/* Right header */}
      <rect x={pad * 2 + colW} y={8} width={colW} height={headerH} rx={3} fill={C.accent} />
      <text x={pad * 2 + colW + colW / 2} y={8 + headerH / 2} textAnchor="middle" dominantBaseline="middle"
        fontSize={9} fill={C.white}>{trunc(rightLabel, 10)}</text>

      {/* Separator */}
      <line x1={width / 2} y1={6} x2={width / 2} y2={height - 16}
        stroke={C.border} strokeWidth={1} strokeDasharray="3,2" />

      {/* Left items */}
      {left.map((n, i) => (
        <text key={i} x={pad + colW / 2} y={38 + i * 15} textAnchor="middle" fontSize={8} fill={C.text}>
          {trunc(n.label, 12)}
        </text>
      ))}

      {/* Right items */}
      {right.map((n, i) => (
        <text key={i} x={pad * 2 + colW + colW / 2} y={38 + i * 15} textAnchor="middle" fontSize={8} fill={C.text}>
          {trunc(n.label, 12)}
        </text>
      ))}

      <Footer label={diagram.title} width={width} height={height} />
    </svg>
  );
};

/* ── generic node list ── */
const NodeList: React.FC<Props> = ({ diagram, width, height }) => {
  const nodes = (diagram.nodes ?? []).slice(0, 6);
  const itemH = 20;
  const totalH = nodes.length * itemH;
  const startY = Math.max(10, (height - totalH - 16) / 2);

  if (!nodes.length) return <Fallback label={diagram.title} width={width} height={height} />;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {nodes.map((node, i) => (
        <g key={node.id ?? i}>
          <rect x={8} y={startY + i * itemH} width={width - 16} height={itemH - 3}
            rx={2} fill={i % 2 === 0 ? C.bg : C.white} stroke={C.border} strokeWidth={0.5} />
          <circle cx={18} cy={startY + i * itemH + (itemH - 3) / 2} r={3} fill={C.primary} />
          <text x={26} y={startY + i * itemH + (itemH - 3) / 2} dominantBaseline="middle"
            fontSize={8.5} fill={C.primary}>
            {trunc(node.label, 24)}
          </text>
        </g>
      ))}
      <Footer label={diagram.title} width={width} height={height} />
    </svg>
  );
};

/* ── architecture: layered blocks ── */
const Architecture: React.FC<Props> = ({ diagram, width, height }) => {
  const raw = diagram as any;
  const layers: Array<{ label: string; items: string[] }> = raw.layers ?? [];
  if (!layers.length) return <Fallback label={diagram.title} width={width} height={height} />;

  const pad = 8;
  const layerH = Math.min(Math.floor((height - 28) / layers.length), 36);
  const layerColors = [C.primary, '#005B96', '#007BC0', '#48A9E6', '#7EC8E3'];

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {layers.map((layer, li) => {
        const y = pad + li * (layerH + 4);
        const fill = layerColors[li % layerColors.length];
        const items = (layer.items ?? []).slice(0, 5);
        const itemW = items.length ? Math.floor((width - 2 * pad - 64) / items.length) : 0;
        return (
          <g key={li}>
            <rect x={pad} y={y} width={56} height={layerH} rx={2} fill={fill} />
            <text x={pad + 28} y={y + layerH / 2} textAnchor="middle" dominantBaseline="middle" fontSize={8} fill={C.white}>
              {trunc(layer.label ?? '', 6)}
            </text>
            {items.map((item, ii) => (
              <g key={ii}>
                <rect x={pad + 60 + ii * (itemW + 3)} y={y + 3} width={itemW} height={layerH - 6} rx={2}
                  fill={C.bg} stroke={C.border} strokeWidth={0.5} />
                <text x={pad + 60 + ii * (itemW + 3) + itemW / 2} y={y + layerH / 2}
                  textAnchor="middle" dominantBaseline="middle" fontSize={7.5} fill={fill}>
                  {trunc(String(item ?? ''), 8)}
                </text>
              </g>
            ))}
          </g>
        );
      })}
      <Footer label={diagram.title} width={width} height={height} />
    </svg>
  );
};

/* ── framework: quadrant / pyramid / funnel ── */
const Framework: React.FC<Props> = ({ diagram, width, height }) => {
  const raw = diagram as any;

  // quadrant / SWOT
  if (raw.quadrants?.length) {
    const qs: Array<{ position: string; label: string; items: string[] }> = raw.quadrants;
    const posMap: Record<string, { x: number; y: number }> = {
      top_left:     { x: 0, y: 0 },
      top_right:    { x: 1, y: 0 },
      bottom_left:  { x: 0, y: 1 },
      bottom_right: { x: 1, y: 1 },
    };
    const pad = 8, gap = 4;
    const qW = (width - 2 * pad - gap) / 2;
    const qH = (height - 28 - 2 * pad - gap) / 2;
    const fills = [C.primary, '#005B96', '#FF6B35', '#48A9E6'];
    return (
      <svg width={width} height={height} style={{ display: 'block' }}>
        {qs.slice(0, 4).map((q, i) => {
          const pos = posMap[q.position] ?? { x: i % 2, y: Math.floor(i / 2) };
          const x = pad + pos.x * (qW + gap);
          const y = pad + pos.y * (qH + gap);
          return (
            <g key={i}>
              <rect x={x} y={y} width={qW} height={qH} rx={2} fill={fills[i % fills.length]} opacity={0.85} />
              <text x={x + qW / 2} y={y + 11} textAnchor="middle" fontSize={8} fill={C.white} fontWeight="bold">
                {trunc(q.label ?? q.position, 10)}
              </text>
              {(q.items ?? []).slice(0, 3).map((item, ii) => (
                <text key={ii} x={x + qW / 2} y={y + 22 + ii * 12} textAnchor="middle" fontSize={7.5} fill={C.white}>
                  {trunc(String(item ?? ''), 12)}
                </text>
              ))}
            </g>
          );
        })}
        <Footer label={diagram.title} width={width} height={height} />
      </svg>
    );
  }

  // pyramid
  if (raw.pyramid_levels?.length) {
    const levels: Array<{ label: string; desc?: string }> = raw.pyramid_levels;
    const n = levels.length;
    const levelH = Math.min(Math.floor((height - 28) / n), 32);
    const pad = 8;
    return (
      <svg width={width} height={height} style={{ display: 'block' }}>
        {levels.map((lvl, i) => {
          const w = Math.floor((width - 2 * pad) * (n - i) / n);
          const x = pad + (width - 2 * pad - w) / 2;
          const y = pad + i * (levelH + 3);
          const opacity = 0.5 + 0.5 * (n - i) / n;
          return (
            <g key={i}>
              <rect x={x} y={y} width={w} height={levelH} rx={2} fill={C.primary} opacity={opacity} />
              <text x={x + w / 2} y={y + levelH / 2} textAnchor="middle" dominantBaseline="middle" fontSize={8} fill={C.white}>
                {trunc(lvl.label ?? '', 14)}
              </text>
            </g>
          );
        })}
        <Footer label={diagram.title} width={width} height={height} />
      </svg>
    );
  }

  // funnel
  if (raw.funnel_stages?.length) {
    const stages: Array<{ label: string; value?: number }> = raw.funnel_stages;
    const n = stages.length;
    const stageH = Math.min(Math.floor((height - 28) / n), 28);
    const pad = 8;
    return (
      <svg width={width} height={height} style={{ display: 'block' }}>
        {stages.map((st, i) => {
          const ratio = 1 - i * 0.15;
          const w = Math.max(Math.floor((width - 2 * pad) * ratio), 40);
          const x = pad + (width - 2 * pad - w) / 2;
          const y = pad + i * (stageH + 3);
          return (
            <g key={i}>
              <rect x={x} y={y} width={w} height={stageH} rx={2} fill={C.accent} opacity={0.7 + 0.3 * (1 - i / n)} />
              <text x={x + w / 2} y={y + stageH / 2} textAnchor="middle" dominantBaseline="middle" fontSize={8} fill={C.white}>
                {trunc(st.label ?? '', 12)}
              </text>
            </g>
          );
        })}
        <Footer label={diagram.title} width={width} height={height} />
      </svg>
    );
  }

  return <NodeList diagram={diagram} width={width} height={height} />;
};

/* ── Fallback ── */
const Fallback: React.FC<{ label: string; width: number; height: number }> = ({ label, width, height }) => (
  <svg width={width} height={height} style={{ display: 'block' }}>
    <rect x={8} y={8} width={width - 16} height={height - 28} rx={4}
      fill={C.bg} stroke={C.primary} strokeWidth={1} strokeDasharray="4,3" />
    <text x={width / 2} y={(height - 28) / 2 + 8} textAnchor="middle" fontSize={10} fill={C.primary}>
      概念图
    </text>
    <Footer label={label} width={width} height={height} />
  </svg>
);

/* ── Footer label ── */
const Footer: React.FC<{ label: string; width: number; height: number }> = ({ label, width, height }) => (
  <text x={width / 2} y={height - 5} textAnchor="middle" fontSize={7.5} fill={C.muted}>
    {trunc(label ?? '', 28)}
  </text>
);

export default DiagramPreview;
