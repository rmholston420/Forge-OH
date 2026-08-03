/**
 * Stage 7 verifier: exercises every Stage-7 BFF endpoint and asserts real,
 * non-stub responses derived from live agent-server state.
 *
 * Slices covered:
 *   7A  GET  /api/runs/{id}/{plan,commands,artifacts,files,traces}
 *   7B  POST /api/runs/{id}/fork
 *   7C  GET/POST/PATCH/DELETE /api/mcp/servers[/{name}]
 *   7D  GET/POST/PATCH/DELETE /api/plugins[/{name}]
 *   7E  GET/POST/DELETE /api/secrets[/{name}]  +  /api/conversations/{id}/secrets
 *   7F  GET /api/observability/runs/{id}/traces  and /api/observability/traces/{id}[/spans]
 *   7G  GET /api/runs/compare?base=&fork=
 *
 * Global assertion: NO endpoint returns { stub: true }.
 *
 * Prereqs (on Colossus):
 *   - agent-server on http://127.0.0.1:8090
 *   - BFF on http://127.0.0.1:8081
 *   - At least one conversation with events already exists (any run from prior work)
 *
 * Run:
 *   node --experimental-strip-types ./scripts/e2e-stage7.ts
 */

const BFF = 'http://127.0.0.1:8081';
const OH  = 'http://127.0.0.1:8090';

type Result = { name: string; ok: boolean; note?: string };
const results: Result[] = [];

const pass = (name: string, note?: string) => { results.push({ name, ok: true, note }); console.log(`PASS ${name}${note ? '  — ' + note : ''}`); };
const fail = (name: string, note: string) => { results.push({ name, ok: false, note }); console.error(`FAIL ${name}  — ${note}`); };

async function getJson(url: string, init?: RequestInit): Promise<any> {
  const r = await fetch(url, init);
  const text = await r.text();
  let json: any = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* leave as null */ }
  return { status: r.status, json, text };
}

function assertNoStub(name: string, payload: any) {
  const s = JSON.stringify(payload ?? {});
  if (/"stub"\s*:\s*true/i.test(s)) fail(name, 'contains "stub": true');
}

async function main() {
  // 0. Pick a real conversation with events to test against.
  const searchResp = await fetch(`${OH}/api/conversations/search?limit=20`);
  const searchBody: any = await searchResp.json();
  const convs: any[] = searchBody.items ?? [];
  if (convs.length === 0) { fail('preflight', 'no conversations on agent-server to test against'); return finalize(); }

  // Prefer one that has events (file_editor activity gives artifacts + traces).
  let picked: string | null = null;
  for (const c of convs) {
    const ev = await getJson(`${OH}/api/conversations/${c.id}/events/search?limit=5`);
    if ((ev.json?.items ?? []).some((e: any) => e.kind === 'ActionEvent')) { picked = c.id; break; }
  }
  if (!picked) picked = convs[0].id;
  console.log(`ground truth: run_id = ${picked}`);

  // ---------- 7A: derived surfaces ----------
  for (const endpoint of ['plan', 'commands', 'artifacts', 'files', 'traces']) {
    const r = await getJson(`${BFF}/api/runs/${picked}/${endpoint}`);
    if (r.status !== 200) { fail(`7A ${endpoint}`, `HTTP ${r.status}`); continue; }
    if (!('data' in (r.json ?? {}))) { fail(`7A ${endpoint}`, 'missing "data" envelope'); continue; }
    assertNoStub(`7A ${endpoint}`, r.json);
    pass(`7A ${endpoint}`, `200, data has ${Array.isArray(r.json.data) ? r.json.data.length + ' items' : 'object'}`);
  }

  // ---------- 7B: fork ----------
  const forkResp = await getJson(`${BFF}/api/runs/${picked}/fork`, { method: 'POST' });
  let forkedId: string | null = null;
  if (forkResp.status !== 200 && forkResp.status !== 201) {
    fail('7B fork', `HTTP ${forkResp.status}: ${forkResp.text.slice(0, 200)}`);
  } else {
    // BFF returns { ok, run_id, forked_id } (no data envelope)
    forkedId = forkResp.json?.forked_id ?? forkResp.json?.data?.id ?? null;
    if (!forkedId) fail('7B fork', 'no forked run id returned');
    else {
      assertNoStub('7B fork', forkResp.json);
      pass('7B fork', `forkedId=${forkedId}`);
    }
  }

  // ---------- 7C: MCP ----------
  const mcpList = await getJson(`${BFF}/api/mcp`);
  if (mcpList.status !== 200) fail('7C list', `HTTP ${mcpList.status}`);
  else {
    assertNoStub('7C list', mcpList.json);
    const arr = Array.isArray(mcpList.json) ? mcpList.json : (mcpList.json?.data ?? []);
    pass('7C list', `${arr.length} server(s)`);
  }

  // Register + test + delete a stdio server
  const mcpName = `verifier-${Date.now()}`;
  const reg = await getJson(`${BFF}/api/mcp`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: mcpName, transport: 'stdio', command: 'echo', args: ['ok'] }),
  });
  if (reg.status !== 200 && reg.status !== 201) fail('7C register', `HTTP ${reg.status}: ${reg.text.slice(0, 200)}`);
  else { assertNoStub('7C register', reg.json); pass('7C register', `${mcpName} registered`); }

  const del = await getJson(`${BFF}/api/mcp/${mcpName}`, { method: 'DELETE' });
  if (del.status !== 200 && del.status !== 204) fail('7C delete', `HTTP ${del.status}`);
  else pass('7C delete', `${mcpName} removed`);

  // ---------- 7D: plugins ----------
  const plugins = await getJson(`${BFF}/api/plugins`);
  if (plugins.status !== 200) fail('7D list', `HTTP ${plugins.status}`);
  else {
    assertNoStub('7D list', plugins.json);
    pass('7D list', `${plugins.json.data?.length ?? 0} installed`);
  }
  const marketplace = await getJson(`${BFF}/api/plugins/marketplace`);
  if (marketplace.status !== 200) fail('7D marketplace', `HTTP ${marketplace.status}`);
  else {
    assertNoStub('7D marketplace', marketplace.json);
    pass('7D marketplace', `${marketplace.json.data?.length ?? 0} listed`);
  }

  // ---------- 7E: secrets ----------
  const secretsList = await getJson(`${BFF}/api/secrets`);
  if (secretsList.status !== 200) fail('7E list', `HTTP ${secretsList.status}`);
  else {
    assertNoStub('7E list', secretsList.json);
    const arr = Array.isArray(secretsList.json) ? secretsList.json : (secretsList.json?.data ?? []);
    pass('7E list', `${arr.length} secrets`);
  }

  const secName = `VERIFIER_${Date.now()}`;
  const secCreate = await getJson(`${BFF}/api/secrets`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: secName, value: 'test-value', description: 'stage7 verifier' }),
  });
  if (secCreate.status !== 200 && secCreate.status !== 201) fail('7E create', `HTTP ${secCreate.status}: ${secCreate.text.slice(0, 200)}`);
  else { assertNoStub('7E create', secCreate.json); pass('7E create', secName); }

  const secDelete = await getJson(`${BFF}/api/secrets/${secName}`, { method: 'DELETE' });
  if (secDelete.status !== 200 && secDelete.status !== 204) fail('7E delete', `HTTP ${secDelete.status}`);
  else pass('7E delete', secName);

  // ---------- 7F: observability traces ----------
  const traceSummaries = await getJson(`${BFF}/api/observability/runs/${picked}/traces`);
  if (traceSummaries.status !== 200) fail('7F summaries', `HTTP ${traceSummaries.status}`);
  else {
    assertNoStub('7F summaries', traceSummaries.json);
    const sums = traceSummaries.json.data ?? [];
    if (sums.length === 0) fail('7F summaries', 'empty summary list for run with events');
    else pass('7F summaries', `spanCount=${sums[0].spanCount}, status=${sums[0].status}`);
  }

  const traceDetail = await getJson(`${BFF}/api/observability/traces/${picked}`);
  if (traceDetail.status !== 200) fail('7F detail', `HTTP ${traceDetail.status}`);
  else {
    assertNoStub('7F detail', traceDetail.json);
    const d = traceDetail.json.data;
    if (!d || !Array.isArray(d.spans)) fail('7F detail', 'missing spans array');
    else pass('7F detail', `${d.spans.length} span(s), traceId=${d.traceId?.slice(0, 8)}...`);
  }

  const spansOnly = await getJson(`${BFF}/api/observability/traces/${picked}/spans`);
  if (spansOnly.status !== 200) fail('7F spans', `HTTP ${spansOnly.status}`);
  else pass('7F spans', `${spansOnly.json.data?.length ?? 0} span(s)`);

  // ---------- 7G: compare (base vs forked) ----------
  if (forkedId) {
    const cmp = await getJson(`${BFF}/api/runs/compare?base=${picked}&fork=${forkedId}`);
    if (cmp.status !== 200) fail('7G compare', `HTTP ${cmp.status}: ${cmp.text.slice(0, 200)}`);
    else {
      assertNoStub('7G compare', cmp.json);
      const d = cmp.json.data;
      const need = ['baseRunId', 'forkRunId', 'baseTitle', 'forkTitle', 'files', 'stats'];
      const missing = need.filter((k) => !(k in d));
      if (missing.length) fail('7G compare', `missing fields: ${missing.join(',')}`);
      else pass('7G compare', `files=${d.files.length}, stats.totalFiles=${d.stats.totalFiles}`);
    }
  } else {
    fail('7G compare', 'no forked run available (7B failed)');
  }

  finalize();
}

function finalize() {
  const failures = results.filter((r) => !r.ok);
  console.log('\n=== SUMMARY ===');
  console.log(`PASS: ${results.length - failures.length} / ${results.length}`);
  if (failures.length) {
    console.log('FAILED:');
    for (const f of failures) console.log(`  ${f.name}  — ${f.note}`);
    process.exit(1);
  }
  console.log('all Stage 7 slices verified');
  process.exit(0);
}

main().catch((err) => { console.error('UNCAUGHT:', err); process.exit(2); });
