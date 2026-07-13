import React from 'react';
import { EmptyState } from '@/components/core/EmptyState';

export default function SecretsPage() {
  return <EmptyState title="Secrets" description="Secrets management coming in Slice 3C. Secret values are never exposed in the browser." icon="🔒" />;
}
