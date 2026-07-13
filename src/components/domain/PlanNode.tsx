'use client';
import React from 'react';
import type { PlanNode as PlanNodeType } from '@/lib/schemas/plan';
import styles from './PlanNode.module.css';

const STATUS_CONFIG: Record<PlanNodeType['status'], { icon: string; label: string; className: string }> = {
  queued:             { icon: '○', label: 'Queued',             className: 'queued' },
  active:             { icon: '▶', label: 'Active',             className: 'active' },
  done:               { icon: '✓',  label: 'Done',               className: 'done' },
  failed:             { icon: '×',  label: 'Failed',             className: 'failed' },
  blocked:            { icon: '■', label: 'Blocked',            className: 'blocked' },
  awaiting_approval:  { icon: '⏸', label: 'Awaiting Approval',  className: 'awaiting' },
};

export interface PlanNodeProps {
  node: PlanNodeType;
  depth?: number;
}

export const PlanNodeItem: React.FC<PlanNodeProps> = ({ node, depth = 0 }) => {
  const cfg = STATUS_CONFIG[node.status];
  return (
    <li
      className={styles.nodeWrapper}
      style={{ paddingLeft: depth > 0 ? `${depth * 16}px` : undefined }}
    >
      <div className={[styles.node, styles[`node--${cfg.className}`]].join(' ')}>
        <span className={styles.icon} aria-hidden="true">{cfg.icon}</span>
        <span className={styles.title}>{node.title}</span>
        <span className={styles.statusLabel}>{cfg.label}</span>
      </div>
      {node.children && node.children.length > 0 && (
        <ul className={styles.children}>
          {node.children.map((child: PlanNodeType) => (
            <PlanNodeItem key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
};
