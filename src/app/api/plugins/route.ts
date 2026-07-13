import { NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search;
  const res = await fetch(`${BFF_URL}/api/plugins${search}`, { cache: 'no-store' });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
