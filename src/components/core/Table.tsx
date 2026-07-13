import React from 'react';
import styles from './Table.module.css';
import { clsx } from 'clsx';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  /** Renders in place of the table body when rows is empty */
  emptyState?: React.ReactNode;
  /** Show a shimmer skeleton while loading */
  loading?: boolean;
  /** Number of skeleton rows to show while loading */
  loadingRowCount?: number;
  className?: string;
  onRowClick?: (row: T) => void;
}

export function Table<T>({
  columns,
  rows,
  getRowKey,
  emptyState,
  loading = false,
  loadingRowCount = 5,
  className,
  onRowClick,
}: TableProps<T>) {
  return (
    <div className={clsx(styles.wrapper, className)} role="region" aria-busy={loading}>
      <table className={styles.table}>
        <thead className={styles.thead}>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(styles.th, col.align && styles[`align-${col.align}`])}
                style={col.width ? { width: col.width } : undefined}
                scope="col"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={styles.tbody}>
          {loading ? (
            Array.from({ length: loadingRowCount }).map((_, i) => (
              <tr key={`skeleton-${i}`} className={styles.tr}>
                {columns.map((col) => (
                  <td key={col.key} className={styles.td}>
                    <span className={styles.skeleton} />
                  </td>
                ))}
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className={styles.emptyCell}>
                {emptyState ?? <span className={styles.emptyDefault}>No items</span>}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={getRowKey(row)}
                className={clsx(styles.tr, onRowClick && styles.clickable)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => { if (e.key === 'Enter' || e.key === ' ') onRowClick(row); }
                    : undefined
                }
                role={onRowClick ? 'button' : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={clsx(styles.td, col.align && styles[`align-${col.align}`])}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
