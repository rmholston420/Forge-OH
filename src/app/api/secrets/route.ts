import { type NextRequest, NextResponse } from 'next/server';

const BFF_URL = process.env.BFF_URL ?? 'http://localhost:8000';

export async function GET(_req: NextRequest) {
  const res = await fetch(`${BFF_URL}/secrets`, {
    headers: { 'x-forge-token': process.env.BFF_SECRET_TOKEN ?? '' },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BFF_URL}/secrets`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-forge-token': process.env.BFF_SECRET_TOKEN ?? '',
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
