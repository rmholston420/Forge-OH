'use client';

import SelfEvalDatePage from '@/features/selfeval/SelfEvalDatePage';

export default function Page({ params }: { params: { date: string } }) {
  // params.date is exposed to us URL-decoded by Next.js. It must match
  // YYYY-MM-DD or the backend will reject the summary filename lookup;
  // we don't sanity-check here because the BFF returns 400 with a clear
  // message the page already surfaces via useCycle.error.
  return <SelfEvalDatePage date={params.date} />;
}
