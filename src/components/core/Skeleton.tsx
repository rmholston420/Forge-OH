import React from 'react';
import styles from './Skeleton.module.css';

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ width = '100%', height = 16, borderRadius, className = '' }) => {
  return (
    <div
      className={[styles.skeleton, className].join(' ')}
      style={{ width, height, borderRadius }}
      aria-hidden="true"
      role="presentation"
    />
  );
};

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({ lines = 3, className }) => {
  return (
    <div className={[styles.skeletonText, className ?? ''].join(' ')} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? '60%' : '100%'} height={12} borderRadius="4px" />
      ))}
    </div>
  );
};
