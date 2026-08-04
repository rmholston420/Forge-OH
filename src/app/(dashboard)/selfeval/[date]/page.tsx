'use client';

import * as React from 'react';
import SelfEvalDatePage from '@/features/selfeval/SelfEvalDatePage';

/**
 * Next.js 16 changed dynamic-route params to a Promise. The prior
 * synchronous signature silently rendered `params.date === undefined`,
 * which made the h1 render as `Cycle: ` and drove `useCycle` to fetch
 * `-selfeval.json` indefinitely. See runs/[runId]/page.tsx for the
 * canonical unwrap pattern used elsewhere in this app.
 */
export default function Page({ params }: { params: Promise<{ date: string }> }) {
  const { date } = React.use(params);
  return <SelfEvalDatePage date={date} />;
}
