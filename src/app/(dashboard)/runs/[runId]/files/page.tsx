'use client';
import React from 'react';
import { FilesTab } from '../tabs/FilesTab';

export default function RunFilesPage({ params }: { params: { runId: string } }) {
  return <FilesTab runId={params.runId} />;
}
