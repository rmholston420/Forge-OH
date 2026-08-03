'use client';
import React from 'react';
import { TerminalTab } from '../tabs/TerminalTab';

export default function RunTerminalPage({ params }: { params: { runId: string } }) {
  return <TerminalTab runId={params.runId} />;
}
