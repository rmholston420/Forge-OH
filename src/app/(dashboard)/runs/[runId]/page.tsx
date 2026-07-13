'use client';

import React from 'react';
import { EmptyState } from '@/components/core/EmptyState';

export default function RunDetailPage({ params }: { params: { runId: string } }) {
  return (
    <EmptyState
      title="Run Detail — coming in Slice 1B"
      description={`Run ID: ${params.runId}. Full event timeline, streaming, and inspector in Phase 1.`}
      icon="⚡"
    />
  );
}
