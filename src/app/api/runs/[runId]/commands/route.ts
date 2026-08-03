import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8081';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  const res = await fetch(`${BFF_URL}/api/runs/${runId}/commands`, { cache: 'no-store' });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
