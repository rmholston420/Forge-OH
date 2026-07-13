import React from 'react';
import styles from './StreamBanner.module.css';

export type StreamState = 'connected' | 'disconnected' | 'reconnecting';

export const StreamBanner: React.FC<{ state: StreamState }> = ({ state }) => {
  if (state === 'connected') return null;
  return (
    <div
      className={[styles.banner, styles[`banner--${state}`]].join(' ')}
      role="status"
      aria-live="polite"
    >
      {state === 'reconnecting' && <span className={styles.pulse} aria-hidden="true" />}
      {state === 'disconnected' && <span aria-hidden="true">⚠️</span>}
      <span>
        {state === 'reconnecting' ? 'Reconnecting to run stream…' : 'Disconnected from run stream'}
      </span>
    </div>
  );
};
