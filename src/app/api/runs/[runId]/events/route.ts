import { type NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  const search = req.nextUrl.searchParams.toString();
  const url = `${BFF_URL}/runs/${runId}/events${search ? `?${search}` : ''}`;
  const res = await fetch(url, {
    headers: { 'x-forge-token': process.env.BFF_SECRET_TOKEN ?? '' },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
