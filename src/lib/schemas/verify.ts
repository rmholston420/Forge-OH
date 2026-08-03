/**
 * Zod schema for VerificationStep, mirroring
 * `openhands_tools_ext/verify/schema.py`.
 *
 * A `VerificationStep` is the structured payload of a verify-loop
 * iteration. It arrives on the frontend as the observation content of a
 * span whose kind is `verify` (tool_name `verify_step` on the BFF).
 *
 * Parity with the Python schema is enforced by
 * `openhands_tools_ext/tests/verify/test_schema_parity.py`.
 */
import { z } from 'zod';

export const VerifyVerdictSchema = z.enum(['pass', 'fail', 'error', 'skipped']);
export type VerifyVerdict = z.infer<typeof VerifyVerdictSchema>;

export const VerifyRunnerSchema = z.enum([
  'pytest',
  'vitest',
  'jest',
  'npm_test',
  'unknown',
]);
export type VerifyRunner = z.infer<typeof VerifyRunnerSchema>;

export const VerificationStepSchema = z.object({
  iteration: z.number().int().min(1),
  max_iterations: z.number().int().min(1),
  runner: VerifyRunnerSchema,
  test_selected: z.array(z.string()).default([]),
  command: z.string().default(''),
  exit_code: z.number().int().nullable().default(null),
  stdout_tail: z.string().default(''),
  stderr_tail: z.string().default(''),
  duration_ms: z.number().int().min(0),
  verdict: VerifyVerdictSchema,
  files_edited_since_last_verify: z.array(z.string()).default([]),
});
export type VerificationStep = z.infer<typeof VerificationStepSchema>;

/**
 * Canonical tool name that anchors verify events on the BFF event stream.
 * Anywhere we key on tool_name for the verify loop, use this constant.
 */
export const VERIFY_STEP_TOOL_NAME = 'verify_step' as const;
