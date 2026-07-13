import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(
  _req: NextRequest,
  { params }: { params: { runId: string } },
) {
  const res = await fetch(`${BFF_URL}/api/runs/${params.runId}/artifacts`, { cache: 'no-store' });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
