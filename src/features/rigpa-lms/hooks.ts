/**
 * React hooks for Rigpa-LMS integration.
 */
'use client';

import { useEffect } from 'react';
import { useRigpaLmsStore } from './store';
import { RigpaAgentLaunchContextSchema } from '@/lib/schemas/rigpa-lms';

/**
 * Reads NEXT_PUBLIC_RIGPA_LMS_CONTEXT env var (JSON) or listens
 * for a postMessage from the LMS iframe host to hydrate context.
 */
export function useRigpaLmsContext() {
  const { context, setContext, setPluginMode } = useRigpaLmsStore();

  useEffect(() => {
    // 1. Check static env injection (server-side embed)
    const envCtx = process.env.NEXT_PUBLIC_RIGPA_LMS_CONTEXT;
    if (envCtx) {
      try {
        const parsed = RigpaAgentLaunchContextSchema.parse(JSON.parse(envCtx));
        setContext(parsed);
        setPluginMode(true);
        return;
      } catch {
        console.warn('[Forge] Invalid NEXT_PUBLIC_RIGPA_LMS_CONTEXT — ignoring');
      }
    }

    // 2. Listen for postMessage from LMS host
    const handler = (event: MessageEvent) => {
      if (event.data?.type !== 'RIGPA_LMS_LAUNCH_CONTEXT') return;
      try {
        const parsed = RigpaAgentLaunchContextSchema.parse(event.data.payload);
        setContext(parsed);
        setPluginMode(true);
      } catch (err) {
        console.warn('[Forge] Invalid RigpaAgentLaunchContext from postMessage', err);
      }
    };

    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [setContext, setPluginMode]);

  return context;
}
