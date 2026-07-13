/**
 * GET  /api/runs       — list runs (paginated, cursor-based)
 * POST /api/runs       — create a new run
 *
 * These handlers proxy to the BFF. In development they return MSW-compatible
 * mock fixtures so the frontend works with zero live services.
 */
import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search;
  const res = await fetch(`${BFF_URL}/api/runs${search}`, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BFF_URL}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
