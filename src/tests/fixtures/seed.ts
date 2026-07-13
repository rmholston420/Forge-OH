/**
 * Deterministic seed data for screenshot and interaction testing.
 * All IDs are fixed — never generate random IDs in fixtures.
 * Fixture files must import from here for ID consistency.
 */

export const SEED = {
  runs: {
    r1: 'run_seed_001',
    r2: 'run_seed_002',
    r3: 'run_seed_003',
  },
  workspaces: {
    w1: 'ws_seed_001',
    w2: 'ws_seed_002',
  },
  agents: {
    a1: 'preset_seed_001',
    a2: 'preset_seed_002',
  },
  events: {
    e1: 'evt_seed_001',
    e2: 'evt_seed_002',
    e3: 'evt_seed_003',
  },
  artifacts: {
    art1: 'art_seed_001',
    art2: 'art_seed_002',
  },
  secrets: {
    s1: 'sec_seed_001',
    s2: 'sec_seed_002',
  },
  plugins: {
    p1: 'plugin_seed_001',
  },
  mcp: {
    m1: 'mcp_seed_001',
    m2: 'mcp_seed_002',
  },
  traces: {
    t1: 'span_seed_001',
    t2: 'span_seed_002',
  },
  lms: {
    session1: 'sess_rigpa_seed001',
    course1: 'RIGPA-CS101',
    module1: 'M3-Functions',
  },
} as const;

export type SeedIds = typeof SEED;
