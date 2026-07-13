/**
 * src/lib/state/index.ts
 *
 * Barrel export for the UI truth state layer.
 */
export { useAppStore } from './app-store';
export type { AppState, AppActions, ActiveRoute } from './app-store';

export { useRunDetailUIStore } from './ui-store';
export type {
  RunDetailUIState,
  RunDetailUIActions,
  RunDetailTab,
  DiffMode,
} from './ui-store';
export {
  selectSelectedTab,
  selectInspectorOpen,
  selectPendingApprovalBanner,
  selectLatestStreamEventId,
} from './ui-store';
