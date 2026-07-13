/**
 * API calls for Rigpa-LMS integration.
 * Feature-flagged: NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED
 */
import type {
  RigpaAgentLaunchContext,
  LmsPackageRequest,
} from '@/lib/schemas/rigpa-lms';

const BASE = '/api';

/**
 * POST /api/lms/context
 * Sends RigpaAgentLaunchContext to BFF for session injection.
 */
export async function injectLmsContext(
  ctx: RigpaAgentLaunchContext
): Promise<{ sessionId: string; injected: boolean }> {
  const res = await fetch(`${BASE}/lms/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ctx),
  });
  if (!res.ok) throw new Error(`Failed to inject LMS context: ${res.status}`);
  return res.json();
}

/**
 * POST /api/lms/package
 * Packages one or more artifacts back to LMS as course objects.
 */
export async function packageArtifactsToLms(
  req: LmsPackageRequest
): Promise<Array<{ artifactId: string; lmsObjectId: string; status: 'packaged' | 'failed'; error?: string }>> {
  const res = await fetch(`${BASE}/lms/package`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to package artifacts: ${res.status}`);
  return res.json();
}

/**
 * GET /api/lms/context/:sessionId
 * Fetches the currently active LMS context for a session.
 */
export async function fetchLmsContext(
  sessionId: string
): Promise<RigpaAgentLaunchContext | null> {
  const res = await fetch(`${BASE}/lms/context/${sessionId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch LMS context: ${res.status}`);
  return res.json();
}
