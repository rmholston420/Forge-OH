'use client';
import React from 'react';
import styles from './MetricKPI.module.css';

export interface MetricKPIProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon?: string;
  loading?: boolean;
}

export const MetricKPI: React.FC<MetricKPIProps> = ({ label, value, unit, trend, trendValue, icon, loading }) => {
  if (loading) {
    return (
      <div className={[styles.card, styles['card--loading']].join(' ')} aria-busy="true">
        <div className={styles.skeleton} style={{ width: '60%', height: 12, marginBottom: 8 }} />
        <div className={styles.skeleton} style={{ width: '80%', height: 28 }} />
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        {icon && <span className={styles.icon}>{icon}</span>}
        <span className={styles.label}>{label}</span>
      </div>
      <div className={styles.valueRow}>
        <span className={styles.value}>{value}</span>
        {unit && <span className={styles.unit}>{unit}</span>}
      </div>
      {trendValue && (
        <div className={[styles.trend, trend ? styles[`trend--${trend}`] : ''].filter(Boolean).join(' ')}>
          {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'} {trendValue}
        </div>
      )}
    </div>
  );
};
