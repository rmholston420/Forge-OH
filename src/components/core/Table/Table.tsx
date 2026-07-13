import React from 'react';
import styles from './Table.module.css';

export interface TableColumn<T> {
  key: keyof T | string;
  header: React.ReactNode;
  render?: (row: T, index: number) => React.ReactNode;
  width?: string;
  align?: 'left' | 'center' | 'right';
  srOnly?: boolean;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  rows: T[];
  getRowKey: (row: T, index: number) => string;
  caption?: string;
  onRowClick?: (row: T) => void;
  selectedRowKey?: string;
  emptyState?: React.ReactNode;
  loading?: boolean;
  className?: string;
  'aria-label'?: string;
}

export function Table<T>({
  columns,
  rows,
  getRowKey,
  caption,
  onRowClick,
  selectedRowKey,
  emptyState,
  loading = false,
  className,
  'aria-label': ariaLabel,
}: TableProps<T>) {
  const isInteractive = Boolean(onRowClick);

  return (
    <div className={[styles.wrapper, className].filter(Boolean).join(' ')} role="region" aria-label={ariaLabel}>
      <table className={styles.table}>
        {caption && <caption className={styles.caption}>{caption}</caption>}
        <thead className={styles.thead}>
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={[styles.th, col.srOnly ? styles.srOnly : ''].join(' ')}
                style={{ width: col.width, textAlign: col.align ?? 'left' }}
                scope="col"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={styles.tbody}>
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <tr key={`skeleton-${i}`} className={styles.row}>
                {columns.map((col) => (
                  <td key={String(col.key)} className={styles.td}>
                    <div className={styles.skeleton} />
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
            rows.map((row, index) => {
              const key = getRowKey(row, index);
              return (
                <tr
                  key={key}
                  className={[
                    styles.row,
                    isInteractive ? styles.rowClickable : '',
                    selectedRowKey === key ? styles.rowSelected : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  tabIndex={isInteractive ? 0 : undefined}
                  onKeyDown={
                    isInteractive
                      ? (e) => { if (e.key === 'Enter' || e.key === ' ') onRowClick!(row); }
                      : undefined
                  }
                  aria-selected={selectedRowKey !== undefined ? selectedRowKey === key : undefined}
                  role={isInteractive ? 'button' : undefined}
                >
                  {columns.map((col) => (
                    <td
                      key={String(col.key)}
                      className={styles.td}
                      style={{ textAlign: col.align ?? 'left' }}
                    >
                      {col.render
                        ? col.render(row, index)
                        : String((row as Record<string, unknown>)[String(col.key)] ?? '')}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
