export type RunEvent = {
  id: string | number;
  eventId?: number | string;
  runId?: string;
  timestamp?: string;
  type: string;
  summary?: string;
  payload?: Record<string, unknown>;
  rawPayload?: Record<string, unknown>;
};

export type RunDetailUIState = {
  selectedTab: 'overview' | 'events' | 'files' | 'artifacts' | 'terminal' | 'browser' | 'metrics' | 'security';
  selectedEventId: string | null;
  selectedArtifactId: string | null;
  diffMode: 'split' | 'unified';
  terminalFilter: 'all' | 'errors' | 'commands';
  inspectorOpen: boolean;
  latestStreamEventId: number;
  pendingApprovalBanner: boolean;
};
