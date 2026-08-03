/**
 * src/tests/unit/schemas-remaining.test.ts
 *
 * Covers workspace, metric, mcp, notification, trace, event, plan,
 * settings, secret schemas. Rewritten to match current production shapes.
 */
import { describe, it, expect } from 'vitest';
import { WorkspaceSchema } from '@/lib/schemas/workspace';
import { MetricSchema } from '@/lib/schemas/metric';
import { McpServerSchema } from '@/lib/schemas/mcp';
import { NotificationSchema } from '@/lib/schemas/notification';
import { TraceSchema, SpanSchema } from '@/lib/schemas/trace';
import { EventSchema } from '@/lib/schemas/event';
import { PlanSchema, PlanStepSchema } from '@/lib/schemas/plan';
import { SettingsSchema } from '@/lib/schemas/settings';
import { SecretSchema } from '@/lib/schemas/secret';

const now = new Date().toISOString();

// ---------------------------------------------------------------------------
// WorkspaceSchema
// ---------------------------------------------------------------------------
describe('WorkspaceSchema', () => {
  const valid = {
    id: 'ws-1',
    name: 'My Workspace',
    type: 'local',
    path: '/home/user/dev/forge-oh/workspaces/my-ws',
    createdAt: now,
  };

  it('parses a valid workspace', () => {
    expect(() => WorkspaceSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing id', () => {
    const { id: _, ...noId } = valid;
    expect(() => WorkspaceSchema.parse(noId)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// MetricSchema
// ---------------------------------------------------------------------------
describe('MetricSchema', () => {
  const valid = {
    runId: 'r1',
    name: 'tokens',
    value: 1000,
    unit: 'count',
    recordedAt: now,
  };

  it('parses a valid metric', () => {
    expect(() => MetricSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing runId', () => {
    const { runId: _, ...rest } = valid;
    expect(() => MetricSchema.parse(rest)).toThrow();
  });

  it('rejects non-number value', () => {
    expect(() => MetricSchema.parse({ ...valid, value: 'big' })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// McpServerSchema
// ---------------------------------------------------------------------------
describe('McpServerSchema', () => {
  const valid = {
    id: 'mcp-1',
    name: 'Context7',
    url: 'https://mcp.example.com',
    enabled: true,
  };

  it('parses a valid MCP server', () => {
    expect(() => McpServerSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing name', () => {
    const { name: _, ...rest } = valid;
    expect(() => McpServerSchema.parse(rest)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// NotificationSchema
// ---------------------------------------------------------------------------
describe('NotificationSchema', () => {
  const valid = {
    id: 'n1',
    title: 'Test',
    body: 'Run completed',
    createdAt: now,
  };

  it('parses a valid notification with defaults', () => {
    expect(() => NotificationSchema.parse(valid)).not.toThrow();
  });

  it('accepts all valid level values', () => {
    for (const level of ['info', 'warning', 'error', 'success']) {
      expect(() => NotificationSchema.parse({ ...valid, level })).not.toThrow();
    }
  });
});

// ---------------------------------------------------------------------------
// SpanSchema / TraceSchema
// ---------------------------------------------------------------------------
describe('SpanSchema', () => {
  const validSpan = {
    spanId: 'sp-1',
    traceId: 'tr-1',
    parentSpanId: null,
    name: 'llm.call',
    kind: 'llm',
    startTime: now,
    endTime: now,
    durationMs: 350,
    status: 'ok',
  };

  it('parses a valid span', () => {
    expect(() => SpanSchema.parse(validSpan)).not.toThrow();
  });

  it('rejects missing spanId', () => {
    const { spanId: _, ...rest } = validSpan;
    expect(() => SpanSchema.parse(rest)).toThrow();
  });
});

describe('TraceSchema', () => {
  const validTrace = {
    traceId: 'tr-1',
    runId: 'r1',
    spans: [],
    startTime: now,
  };

  it('parses a valid trace', () => {
    expect(() => TraceSchema.parse(validTrace)).not.toThrow();
  });

  it('rejects missing traceId', () => {
    const { traceId: _, ...rest } = validTrace;
    expect(() => TraceSchema.parse(rest)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// EventSchema
// ---------------------------------------------------------------------------
describe('EventSchema', () => {
  const valid = {
    id: 1,
    runId: 'r1',
    type: 'tool_call',
    timestamp: now,
  };

  it('parses a valid event', () => {
    expect(() => EventSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing type', () => {
    const { type: _, ...rest } = valid;
    expect(() => EventSchema.parse(rest)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// PlanStepSchema + PlanSchema
// ---------------------------------------------------------------------------
describe('PlanStepSchema', () => {
  const validStep = {
    id: 'step-1',
    planId: 'plan-1',
    title: 'Write tests',
    status: 'pending',
    order: 0,
  };

  it('parses a valid step', () => {
    expect(() => PlanStepSchema.parse(validStep)).not.toThrow();
  });

  it('accepts completed step', () => {
    expect(() => PlanStepSchema.parse({ ...validStep, status: 'completed' })).not.toThrow();
  });

  it('rejects invalid status', () => {
    expect(() => PlanStepSchema.parse({ ...validStep, status: 'exploding' })).toThrow();
  });
});

describe('PlanSchema', () => {
  const validPlan = {
    id: 'plan-1',
    runId: 'r1',
    steps: [],
    status: 'in_progress',
  };

  it('parses a valid plan', () => {
    expect(() => PlanSchema.parse(validPlan)).not.toThrow();
  });

  it('rejects missing runId', () => {
    const { runId: _, ...rest } = validPlan;
    expect(() => PlanSchema.parse(rest)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// SettingsSchema
// ---------------------------------------------------------------------------
describe('SettingsSchema', () => {
  it('parses minimal settings object (all defaults)', () => {
    expect(() => SettingsSchema.parse({})).not.toThrow();
  });

  it('rejects non-object input', () => {
    expect(() => SettingsSchema.parse('string-settings')).toThrow();
  });
});

// ---------------------------------------------------------------------------
// SecretSchema
// ---------------------------------------------------------------------------
describe('SecretSchema', () => {
  const valid = {
    id: 's1',
    name: 'OPENAI_API_KEY',
    scope: 'global',
    createdAt: now,
  };

  it('parses a valid secret', () => {
    expect(() => SecretSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing name', () => {
    const { name: _, ...rest } = valid;
    expect(() => SecretSchema.parse(rest)).toThrow();
  });

  it('rejects invalid scope', () => {
    expect(() => SecretSchema.parse({ ...valid, scope: 'universe' })).toThrow();
  });

  it('accepts all valid scopes', () => {
    for (const scope of ['global', 'workspace', 'run']) {
      expect(() => SecretSchema.parse({ ...valid, scope })).not.toThrow();
    }
  });

  it('does NOT have a rawValue field in the schema (security contract)', () => {
    const parsed = SecretSchema.parse(valid);
    expect(parsed).not.toHaveProperty('rawValue');
  });
});
