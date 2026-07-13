'use client';
import React from 'react';
import { useBrowserFrames } from '@/features/browser/hooks';
import { BrowserViewer } from '@/components/domain/BrowserViewer';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_BROWSER_ENABLED !== 'false';

export function BrowserTab({ runId, isActive }: { runId: string; isActive: boolean }) {
  const { data: frames = [], isLoading, error } = useBrowserFrames(runId, isActive);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Browser tab is feature-flagged. Set NEXT_PUBLIC_FEATURE_BROWSER_ENABLED=true.</Banner>;
  }

  if (isLoading) return <Skeleton width="100%" height={480} borderRadius="12px" />;

  if (error) return <Banner variant="error">Failed to load browser frames.</Banner>;

  return <BrowserViewer frames={frames} isActive={isActive} />;
}

export default BrowserTab;
