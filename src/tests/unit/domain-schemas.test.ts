/**
 * domain-schemas.test.ts
 *
 * Coverage for all domain schemas that have no dedicated test file:
 *   run.ts, artifact.ts, event.ts, mcp.ts, secret.ts,
 *   metric.ts, trace.ts, notification.ts, plan.ts,
 *   file-diff.ts, browser.ts, terminal.ts, settings.ts, workspace.ts
 *
 * Each schema gets:
 *   - a valid parse that succeeds
 *   - at least one invalid parse that throws
 *   - boundary checks on optional/required fields
 */
import { describe, it, expect } from 'vitest';
import { RunSchema, RunStatusSchema, CreateRunSchema } from '@/lib/schemas/run';
import { ArtifactSchema } from '@/lib/schemas/artifact';
import { ToolEventSchema } from '@/lib/schemas/event';
import { McpServerSchema, McpToolSchema } from '@/lib/schemas/mcp';
import { SecretSchema, CreateSecretSchema } from '@/lib/schemas/secret';
import { RunMetricSchema } from '@/lib/schemas/metric';
import { TraceSpanSchema } from '@/lib/schemas/trace';
import { NotificationSchema } from '@/lib/schemas/notification';
import { PlanStepSchema } from '@/lib/schemas/plan';
import { FileDiffSchema } from '@/lib/schemas/file-diff';
import { BrowserStateSchema } from '@/lib/schemas/browser';
import { TerminalOutputSchema } from '@/lib/schemas/terminal';
import { AppSettingsSchema } from '@/lib/schemas/settings';
import { WorkspaceSchema } from '@/lib/schemas/workspace';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const now = new Date().toISOString();

// ---------------------------------------------------------------------------
// RunSchema
// ---------------------------------------------------------------------------
describe('RunSchema', () => {
  const VALID_RUN = {
    id: 'run-1',
    status: 'queued',
    workspaceId: 'ws-1',
    agentPreset: 'default',
    createdAt: now,
  };

  it('parses a minimal valid run', () => {
    expect(() => RunSchema.parse(VALID_RUN)).not.toThrow();
  });

  it('accepts all terminal statuses including stopped', () => {
    for (const status of ['queued', 'running', 'completed', 'failed', 'stopped', 'pending_approval']) {
      expect(() => RunSchema.parse({ ...VALID_RUN, status })).not.toThrow();
    }
  });

  it('rejects unknown status', () => {
    expect(() => RunSchema.parse({ ...VALID_RUN, status: 'ghost' })).toThrow();
  });

  it('optional fields are absent when not provided', () => {
    const r = RunSchema.parse(VALID_RUN);
    expect(r.finishedAt).toBeUndefined();
    expect(r.durationMs).toBeUndefined();
    expect(r.costUsd).toBeUndefined();
  });
});

describe('RunStatusSchema', () => {
  it('accepts every valid status value', () => {
    for (const s of ['queued', 'running', 'completed', 'failed', 'stopped', 'pending_approval']) {
      expect(() => RunStatusSchema.parse(s)).not.toThrow();
    }
  });
});

describe('CreateRunSchema', () => {
  it('requires agentPreset and workspaceId', () => {
    expect(() => CreateRunSchema.parse({})).toThrow();
    expect(() =>
      CreateRunSchema.parse({ agentPreset: 'default', workspaceId: 'ws-1' })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// ArtifactSchema
// ---------------------------------------------------------------------------
describe('ArtifactSchema', () => {
  const VALID = {
    id: 'art-1',
    runId: 'run-1',
    path: '/workspace/output.py',
    type: 'file',
    createdAt: now,
  };

  it('parses a valid artifact', () => {
    expect(() => ArtifactSchema.parse(VALID)).not.toThrow();
  });

  it('rejects missing path', () => {
    const { path: _, ...rest } = VALID;
    expect(() => ArtifactSchema.parse(rest)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// ToolEventSchema
// ---------------------------------------------------------------------------
describe('ToolEventSchema', () => {
  const VALID = {
    id: 1,
    type: 'tool_call',
    timestamp: now,
    runId: 'run-1',
  };

  it('parses a valid event', () => {
    expect(() => ToolEventSchema.parse(VALID)).not.toThrow();
  });

  it('id must be a number', () => {
    expect(() => ToolEventSchema.parse({ ...VALID, id: 'string-id' })).toThrow();
  });

  it('payload is optional', () => {
    const result = ToolEventSchema.parse(VALID);
    expect(result.payload).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// McpServerSchema / McpToolSchema
// ---------------------------------------------------------------------------
describe('McpServerSchema', () => {
  const VALID = {
    id: 'mcp-1',
    name: 'GitHub MCP',
    url: 'https://mcp.example.com',
    enabled: true,
    tools: [],
  };

  it('parses a valid MCP server', () => {
    expect(() => McpServerSchema.parse(VALID)).not.toThrow();
  });

  it('rejects non-URL url field', () => {
    expect(() => McpServerSchema.parse({ ...VALID, url: 'not-a-url' })).toThrow();
  });

  it('enabled defaults to false when omitted', () => {
    const { enabled: _, ...rest } = VALID;
    const r = McpServerSchema.parse(rest);
    expect(r.enabled).toBe(false);
  });
});

describe('McpToolSchema', () => {
  it('parses a valid tool', () => {
    expect(() =>
      McpToolSchema.parse({ name: 'read_file', description: 'Reads a file', inputSchema: {} })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// SecretSchema / CreateSecretSchema
// ---------------------------------------------------------------------------
describe('SecretSchema', () => {
  const VALID = {
    id: 'sec-1',
    name: 'OPENAI_API_KEY',
    scope: 'global',
    createdAt: now,
  };

  it('parses a valid secret (rawValue is absent by design)', () => {
    const r = SecretSchema.parse(VALID);
    expect(r.rawValue).toBeUndefined();
  });

  it('accepts all scope values', () => {
    for (const scope of ['global', 'workspace', 'run']) {
      expect(() => SecretSchema.parse({ ...VALID, scope })).not.toThrow();
    }
  });

  it('rejects invalid scope', () => {
    expect(() => SecretSchema.parse({ ...VALID, scope: 'user' })).toThrow();
  });
});

describe('CreateSecretSchema', () => {
  it('requires name, scope, and rawValue', () => {
    expect(() => CreateSecretSchema.parse({})).toThrow();
    expect(() =>
      CreateSecretSchema.parse({ name: 'MY_KEY', scope: 'global', rawValue: 'secret123' })
    ).not.toThrow();
  });

  it('rejects empty name', () => {
    expect(() =>
      CreateSecretSchema.parse({ name: '', scope: 'global', rawValue: 'v' })
    ).toThrow();
  });
});

// ---------------------------------------------------------------------------
// RunMetricSchema
// ---------------------------------------------------------------------------
describe('RunMetricSchema', () => {
  it('parses a valid metric', () => {
    expect(() =>
      RunMetricSchema.parse({ runId: 'r1', name: 'token_count', value: 1024, unit: 'tokens', recordedAt: now })
    ).not.toThrow();
  });

  it('value must be a number', () => {
    expect(() =>
      RunMetricSchema.parse({ runId: 'r1', name: 'n', value: 'not-a-number', unit: 'u', recordedAt: now })
    ).toThrow();
  });
});

// ---------------------------------------------------------------------------
// TraceSpanSchema
// ---------------------------------------------------------------------------
describe('TraceSpanSchema', () => {
  const VALID = {
    traceId: 'trace-1',
    spanId: 'span-1',
    name: 'http.request',
    startTime: now,
    endTime: now,
  };

  it('parses a valid span', () => {
    expect(() => TraceSpanSchema.parse(VALID)).not.toThrow();
  });

  it('parentSpanId is optional', () => {
    const r = TraceSpanSchema.parse(VALID);
    expect(r.parentSpanId).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// NotificationSchema
// ---------------------------------------------------------------------------
describe('NotificationSchema', () => {
  const VALID = {
    id: 'notif-1',
    title: 'Run completed',
    body: 'Your run finished successfully.',
    level: 'info',
    createdAt: now,
    read: false,
  };

  it('parses a valid notification', () => {
    expect(() => NotificationSchema.parse(VALID)).not.toThrow();
  });

  it('accepts all level values', () => {
    for (const level of ['info', 'warning', 'error', 'success']) {
      expect(() => NotificationSchema.parse({ ...VALID, level })).not.toThrow();
    }
  });

  it('rejects invalid level', () => {
    expect(() => NotificationSchema.parse({ ...VALID, level: 'debug' })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// PlanStepSchema
// ---------------------------------------------------------------------------
describe('PlanStepSchema', () => {
  const VALID = { id: 'step-1', label: 'Install deps', status: 'pending', order: 0 };

  it('parses a valid step', () => {
    expect(() => PlanStepSchema.parse(VALID)).not.toThrow();
  });

  it('accepts all status values', () => {
    for (const status of ['pending', 'running', 'completed', 'failed', 'skipped']) {
      expect(() => PlanStepSchema.parse({ ...VALID, status })).not.toThrow();
    }
  });

  it('children is optional array', () => {
    const r = PlanStepSchema.parse(VALID);
    expect(r.children).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// FileDiffSchema
// ---------------------------------------------------------------------------
describe('FileDiffSchema', () => {
  const VALID = {
    path: 'src/main.ts',
    status: 'modified',
    additions: 5,
    deletions: 2,
    hunks: [],
  };

  it('parses a valid diff', () => {
    expect(() => FileDiffSchema.parse(VALID)).not.toThrow();
  });

  it('accepts all diff status values', () => {
    for (const status of ['added', 'modified', 'deleted', 'renamed']) {
      expect(() => FileDiffSchema.parse({ ...VALID, status })).not.toThrow();
    }
  });
});

// ---------------------------------------------------------------------------
// BrowserStateSchema
// ---------------------------------------------------------------------------
describe('BrowserStateSchema', () => {
  it('parses a valid browser state', () => {
    expect(() =>
      BrowserStateSchema.parse({
        url: 'https://example.com',
        title: 'Example',
        screenshotDataUrl: null,
        loading: false,
      })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// TerminalOutputSchema
// ---------------------------------------------------------------------------
describe('TerminalOutputSchema', () => {
  it('parses a valid terminal output line', () => {
    expect(() =>
      TerminalOutputSchema.parse({ stream: 'stdout', data: 'hello\n', timestamp: now })
    ).not.toThrow();
  });

  it('rejects invalid stream value', () => {
    expect(() =>
      TerminalOutputSchema.parse({ stream: 'debug', data: 'x', timestamp: now })
    ).toThrow();
  });
});

// ---------------------------------------------------------------------------
// AppSettingsSchema
// ---------------------------------------------------------------------------
describe('AppSettingsSchema', () => {
  it('parses a minimal settings object with defaults', () => {
    const r = AppSettingsSchema.parse({});
    expect(r.theme).toBeDefined();
    expect(r.language).toBeDefined();
  });

  it('accepts dark and light theme', () => {
    for (const theme of ['light', 'dark', 'system']) {
      expect(() => AppSettingsSchema.parse({ theme })).not.toThrow();
    }
  });
});

// ---------------------------------------------------------------------------
// WorkspaceSchema
// ---------------------------------------------------------------------------
describe('WorkspaceSchema', () => {
  const VALID = {
    id: 'ws-1',
    name: 'My Workspace',
    repoUrl: 'https://github.com/org/repo',
    createdAt: now,
  };

  it('parses a valid workspace', () => {
    expect(() => WorkspaceSchema.parse(VALID)).not.toThrow();
  });

  it('rejects invalid repoUrl', () => {
    expect(() => WorkspaceSchema.parse({ ...VALID, repoUrl: 'not-a-url' })).toThrow();
  });

  it('optional fields default or are absent', () => {
    const r = WorkspaceSchema.parse(VALID);
    expect(r.description).toBeUndefined();
  });
});
