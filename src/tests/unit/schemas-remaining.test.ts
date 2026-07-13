/**
 * src/tests/unit/schemas-remaining.test.ts
 *
 * Covers the 9 schemas not yet tested in schemas.test.ts:
 *   WorkspaceSchema, MetricSchema, McpServerSchema,
 *   NotificationSchema, TraceSchema + SpanSchema,
 *   EventSchema, PlanSchema + PlanStepSchema,
 *   SettingsSchema, SecretSchema
 *
 * Strategy per schema:
 *   1. Parse a minimal valid fixture → expect success
 *   2. Omit a required field → expect failure
 *   3. Assert key discriminant / enum constraints
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

// ---------------------------------------------------------------------------
// WorkspaceSchema
// ---------------------------------------------------------------------------
describe('WorkspaceSchema', () => {
  const valid = {
    id: 'ws-1',
    name: 'My Workspace',
    type: 'local',
    status: 'idle',
    diskUsageMb: 0,
    runCount: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  it('parses a valid workspace', () => {
    expect(() => WorkspaceSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing id', () => {
    expect(() => WorkspaceSchema.parse({ ...valid, id: undefined })).toThrow();
  });

  it('rejects invalid status', () => {
    expect(() => WorkspaceSchema.parse({ ...valid, status: 'flying' })).toThrow();
  });

  it('rejects non-number diskUsageMb', () => {
    expect(() => WorkspaceSchema.parse({ ...valid, diskUsageMb: 'big' })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// MetricSchema
// ---------------------------------------------------------------------------
describe('MetricSchema', () => {
  const valid = {
    runId: 'r1',
    totalTokens: 1000,
    costUsd: 0.042,
    durationMs: 5000,
    stepsCompleted: 3,
    stepsFailed: 0,
  };

  it('parses a valid metric', () => {
    expect(() => MetricSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing runId', () => {
    expect(() => MetricSchema.parse({ ...valid, runId: undefined })).toThrow();
  });

  it('accepts null costUsd (run may not have cost yet)', () => {
    expect(() => MetricSchema.parse({ ...valid, costUsd: null })).not.toThrow();
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
    status: 'connected',
    enabled: true,
  };

  it('parses a valid MCP server', () => {
    expect(() => McpServerSchema.parse(valid)).not.toThrow();
  });

  it('rejects invalid URL format', () => {
    expect(() => McpServerSchema.parse({ ...valid, url: 'not-a-url' })).toThrow();
  });

  it('rejects missing name', () => {
    expect(() => McpServerSchema.parse({ ...valid, name: undefined })).toThrow();
  });

  it('rejects invalid status enum', () => {
    expect(() => McpServerSchema.parse({ ...valid, status: 'flying' })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// NotificationSchema
// ---------------------------------------------------------------------------
describe('NotificationSchema', () => {
  const valid = {
    id: 'n1',
    type: 'info',
    message: 'Run completed',
    read: false,
    createdAt: new Date().toISOString(),
  };

  it('parses a valid notification', () => {
    expect(() => NotificationSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing message', () => {
    expect(() => NotificationSchema.parse({ ...valid, message: undefined })).toThrow();
  });

  it('rejects invalid type enum', () => {
    expect(() => NotificationSchema.parse({ ...valid, type: 'critical-alert' })).toThrow();
  });

  it('accepts all valid type values', () => {
    for (const type of ['info', 'warning', 'error', 'success']) {
      expect(() => NotificationSchema.parse({ ...valid, type })).not.toThrow();
    }
  });
});

// ---------------------------------------------------------------------------
// TraceSchema + SpanSchema
// ---------------------------------------------------------------------------
describe('SpanSchema', () => {
  const validSpan = {
    spanId: 'sp-1',
    traceId: 'tr-1',
    name: 'llm.call',
    startTime: new Date().toISOString(),
    endTime: new Date().toISOString(),
    durationMs: 350,
    status: 'ok',
  };

  it('parses a valid span', () => {
    expect(() => SpanSchema.parse(validSpan)).not.toThrow();
  });

  it('rejects missing spanId', () => {
    expect(() => SpanSchema.parse({ ...validSpan, spanId: undefined })).toThrow();
  });
});

describe('TraceSchema', () => {
  const validTrace = {
    traceId: 'tr-1',
    runId: 'r1',
    spans: [],
    startTime: new Date().toISOString(),
  };

  it('parses a valid trace', () => {
    expect(() => TraceSchema.parse(validTrace)).not.toThrow();
  });

  it('rejects missing traceId', () => {
    expect(() => TraceSchema.parse({ ...validTrace, traceId: undefined })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// EventSchema
// ---------------------------------------------------------------------------
describe('EventSchema', () => {
  const valid = {
    id: 'ev-1',
    runId: 'r1',
    type: 'message',
    payload: {},
    createdAt: new Date().toISOString(),
  };

  it('parses a valid event', () => {
    expect(() => EventSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing type', () => {
    expect(() => EventSchema.parse({ ...valid, type: undefined })).toThrow();
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
    expect(() => PlanSchema.parse({ ...validPlan, runId: undefined })).toThrow();
  });
});

// ---------------------------------------------------------------------------
// SettingsSchema
// ---------------------------------------------------------------------------
describe('SettingsSchema', () => {
  it('parses minimal settings object', () => {
    // Settings may have all optional fields — parse empty object at minimum
    expect(() => SettingsSchema.parse({})).not.toThrow();
  });

  it('rejects non-object input', () => {
    expect(() => SettingsSchema.parse('string-settings')).toThrow();
    expect(() => SettingsSchema.parse(null)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// SecretSchema
// ---------------------------------------------------------------------------
describe('SecretSchema', () => {
  const valid = {
    id: 's1',
    key: 'OPENAI_API_KEY',
    scope: 'global',
    createdAt: new Date().toISOString(),
  };

  it('parses a valid secret', () => {
    expect(() => SecretSchema.parse(valid)).not.toThrow();
  });

  it('rejects missing key', () => {
    expect(() => SecretSchema.parse({ ...valid, key: undefined })).toThrow();
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
