'use client';
import React from 'react';
import { PlanNodeItem } from './PlanNode';
import { Skeleton } from '@/components/core/Skeleton';
import { EmptyState } from '@/components/core/EmptyState';
import type { PlanNode } from '@/lib/schemas/plan';
import styles from './PlanRail.module.css';

export interface PlanRailProps {
  nodes: PlanNode[];
  loading?: boolean;
}

export const PlanRail: React.FC<PlanRailProps> = ({ nodes, loading }) => {
  return (
    <aside className={styles.rail} aria-label="Plan steps">
      <div className={styles.header}>
        <span className={styles.title}>Plan</span>
        {nodes.length > 0 && (
          <span className={styles.progress}>
            {nodes.filter((n) => n.status === 'done').length}/{nodes.length}
          </span>
        )}
      </div>
      {loading && (
        <div className={styles.skeletonList}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={styles.skeletonNode}>
              <Skeleton width={16} height={16} borderRadius="50%" />
              <Skeleton width={`${60 + i * 10}%`} height={12} />
            </div>
          ))}
        </div>
      )}
      {!loading && nodes.length === 0 && (
        <EmptyState
          title="No plan yet"
          description="Plan steps will appear as the agent plans its work."
          icon="📋"
        />
      )}
      {nodes.length > 0 && (
        <ul className={styles.list}>
          {nodes.map((node) => (
            <PlanNodeItem key={node.id} node={node} />
          ))}
        </ul>
      )}
    </aside>
  );
};
