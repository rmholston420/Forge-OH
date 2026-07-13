'use client';
import React, { useCallback, useRef } from 'react';
import { useRunDetail, useRunEvents } from '@/features/run-detail/hooks';
import { useRunDetailStore } from '@/features/run-detail/store';
import { useRunStream } from '@/lib/streaming/useRunStream';
import type { StreamEvent } from '@/lib/streaming/useRunStream';
import { RunDetailHeader } from '@/components/domain/RunDetailHeader';
import { EventCard } from '@/components/domain/EventCard';
import { StreamBanner } from '@/components/domain/StreamBanner';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import { EmptyState } from '@/components/core/EmptyState';
import { Tabs } from '@/components/core/Tabs';
import BrowserTab from './tabs/BrowserTab';
import MetricsTab from './tabs/MetricsTab';
import SecurityTab from './tabs/SecurityTab';
import TraceTab from './tabs/TraceTab';
import styles from './run-detail.module.css';

// Tab definitions must stay in sync with:
//   - RunDetailStore['selectedTab'] in src/features/run-detail/store.ts
//   - RunDetailUIStateSchema.selectedTab in src/lib/schemas/run.ts
const TABS = [
  { id: 'overview',  label: 'Overview'  },
  { id: 'files',     label: 'Files'     },
  { id: 'terminal',  label: 'Terminal'  },
  { id: 'browser',   label: 'Browser'   },
  { id: 'metrics',   label: 'Metrics'   },
  { id: 'security',  label: 'Security'  },
  { id: 'trace',     label: 'Trace'     },
];

type DisplayEvent = {
  id: string | number;
  type: string;
  timestamp: string;
  eventId?: string | number;
  runId?: string;
  source?: string;
  payload?: Record<string, unknown>;
  rawPayload?: Record<string, unknown>;
  summary?: string;
  raw?: unknown;
};

const toDisplayEvent = (event: unknown): DisplayEvent => {
  const e = (event ?? {}) as Record<string, unknown>;
  return {
    id: (e.id ?? e.eventId ?? `evt:${Date.now()}`) as string | number,
    type: String(e.type ?? 'message'),
    timestamp: String(e.timestamp ?? new Date().toISOString()),
    eventId: e.eventId as string | number | undefined,
    runId: e.runId as string | undefined,
    source: e.source as string | undefined,
    payload: (e.payload as Record<string, unknown> | undefined) ?? {},
    rawPayload: (e.rawPayload as Record<string, unknown> | undefined) ?? {},
    summary: e.summary as string | undefined,
    raw: e.raw,
  };
};

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = React.use(params);
  const { data: run, isLoading: runLoading, error: runError } = useRunDetail(runId);
  const { data: bootstrapEvents = [] } = useRunEvents(runId);

  const {
    selectedTab, setSelectedTab,
    selectedEventId, setSelectedEventId,
    streamEvents, appendStreamEvent,
    streamConnected, setStreamConnected,
    streamReconnecting, setStreamReconnecting,
    setPendingApprovalBanner, pendingApprovalBanner,
    latestStreamEventId,
  } = useRunDetailStore();

  // handleEvent uses StreamEvent (the socket wire type) — not ToolEvent.
  // Previously typed as ToolEvent which caused a silent schema mismatch.
  const handleEvent = useCallback((evt: StreamEvent) => {
    appendStreamEvent(evt as Record<string, unknown>);
    if (evt.type === 'error') setPendingApprovalBanner(false);
  }, [appendStreamEvent, setPendingApprovalBanner]);

  // Stabilize inline callbacks so the socket doesn't reconnect on every render.
  // useRunStream does this internally via refs, but we also keep local refs for
  // clarity and for any future direct use.
  const setStreamConnectedRef = useRef(setStreamConnected);
  const setStreamReconnectingRef = useRef(setStreamReconnecting);
  setStreamConnectedRef.current = setStreamConnected;
  setStreamReconnectingRef.current = setStreamReconnecting;

  useRunStream({
    runId,
    latestEventId: latestStreamEventId,
    onEvent: handleEvent,
    onConnected: useCallback(() => {
      setStreamConnectedRef.current(true);
      setStreamReconnectingRef.current(false);
    }, []),
    onDisconnected: useCallback(() => setStreamConnectedRef.current(false), []),
    onReconnecting: useCallback(() => setStreamReconnectingRef.current(true), []),
  });

  const allEvents = [
    ...bootstrapEvents,
    ...streamEvents.filter((se) => !bootstrapEvents.find((be) => be.id === se.id)),
  ];

  const streamState = streamReconnecting ? 'reconnecting' : streamConnected ? 'connected' : 'disconnected';

  if (runError) {
    return (
      <Banner variant="error">
        Failed to load run: {runError instanceof Error ? runError.message : 'Unknown error'}
      </Banner>
    );
  }

  return (
    <div className={styles.page}>
      {runLoading ? (
        <div className={styles.headerSkeleton}>
          <Skeleton width="50%" height={20} />
          <Skeleton width="30%" height={14} />
        </div>
      ) : run ? (
        <RunDetailHeader
          run={run}
          onApprove={() => setPendingApprovalBanner(false)}
        />
      ) : null}

      {pendingApprovalBanner && (
        <Banner variant="warning" title="Awaiting Approval">
          The agent has paused and is waiting for your approval before proceeding.
        </Banner>
      )}

      <StreamBanner state={streamState} />

      <Tabs
        tabs={TABS}
        activeTab={selectedTab}
        onTabChange={(t) => setSelectedTab(t as RunDetailStore['selectedTab'])}
        variant="underline"
      />

      {/* Overview — event timeline + inspector */}
      {selectedTab === 'overview' && (
        <div className={styles.timelineLayout}>
          <div className={styles.timeline}>
            {runLoading && (
              <div className={styles.skeletonList}>
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className={styles.skeletonEvent}>
                    <Skeleton width={24} height={24} borderRadius="50%" />
                    <div style={{ flex: 1 }}><Skeleton width="80%" height={14} /></div>
                  </div>
                ))}
              </div>
            )}
            {!runLoading && allEvents.length === 0 && (
              <EmptyState
                title="No events yet"
                description="Events will appear here as the agent runs."
                icon="⚡"
              />
            )}
            {allEvents.map((evt, i) => (
              <EventCard
                key={String(evt.id)}
                event={toDisplayEvent(evt)}
                selected={selectedEventId === evt.id}
                highlight={i === allEvents.length - 1 && streamEvents.includes(evt)}
                onSelect={setSelectedEventId}
              />
            ))}
          </div>

          {selectedEventId && (
            <aside className={styles.inspector} aria-label="Event inspector">
              {(() => {
                const ev = allEvents.find((e) => e.id === selectedEventId);
                const displayEv = ev ? toDisplayEvent(ev) : null;
                if (!ev || !displayEv) return null;
                return (
                  <div className={styles.inspectorContent}>
                    <div className={styles.inspectorHeader}>
                      <span className={styles.inspectorTitle}>Event Detail</span>
                      <button
                        className={styles.inspectorClose}
                        onClick={() => setSelectedEventId(null)}
                        aria-label="Close inspector"
                      >×</button>
                    </div>
                    <dl className={styles.dl}>
                      <dt>Type</dt><dd>{String(displayEv.type)}</dd>
                      <dt>Source</dt><dd>{String(displayEv.source ?? 'system')}</dd>
                      <dt>Timestamp</dt><dd>{new Date(String(displayEv.timestamp)).toLocaleString()}</dd>
                      <dt>Summary</dt><dd>{String(displayEv.summary ?? '')}</dd>
                    </dl>
                    {Boolean(displayEv.raw) && (
                      <pre className={styles.inspectorRaw}>
                        {typeof displayEv.raw === 'string' ? displayEv.raw : JSON.stringify(displayEv.raw ?? {}, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })()}
            </aside>
          )}
        </div>
      )}

      {/* Files — Phase 1 (Slice 1B) */}
      {selectedTab === 'files' && (
        <EmptyState
          title="Files"
          description="File diff view will be available in Phase 1."
          icon="📁"
        />
      )}

      {/* Terminal — Phase 1 (Slice 1C) */}
      {selectedTab === 'terminal' && (
        <EmptyState
          title="Terminal"
          description="Terminal output will be available in Phase 1."
          icon="⌨️"
        />
      )}

      {/* Browser — Phase 1 (Slice 2A) */}
      {selectedTab === 'browser' && (
        <BrowserTab runId={runId} />
      )}

      {/* Metrics — Phase 1 (Slice 3A) */}
      {selectedTab === 'metrics' && (
        <MetricsTab runId={runId} />
      )}

      {/* Security — Phase 1 (Slice 3B) */}
      {selectedTab === 'security' && (
        <SecurityTab runId={runId} />
      )}

      {/* Trace — Phase 1 (Slice 4A) */}
      {selectedTab === 'trace' && (
        <TraceTab runId={runId} />
      )}
    </div>
  );
}

// Explicit re-export of store type so callers don't have to import from two places
export type { RunDetailStore } from '@/features/run-detail/store';
