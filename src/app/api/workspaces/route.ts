import { type NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(_req: NextRequest) {
  const res = await fetch(`${BFF_URL}/workspaces`, {
    headers: { 'x-forge-token': process.env.BFF_SECRET_TOKEN ?? '' },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
