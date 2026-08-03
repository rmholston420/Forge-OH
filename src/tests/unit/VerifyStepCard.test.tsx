import { render, screen } from '@testing-library/react';
import { VerifyStepCard } from '@/components/domain/VerifyStepCard';
import type { TraceSpan } from '@/lib/schemas/trace';

function makeSpan(
  attributes: Record<string, unknown>,
  overrides: Partial<TraceSpan> = {},
): TraceSpan {
  return {
    spanId: 's1',
    traceId: 't1',
    parentSpanId: null,
    name: 'verify_step',
    kind: 'verify',
    startTime: new Date().toISOString(),
    endTime: null,
    durationMs: null,
    status: 'ok',
    attributes,
    children: [],
    ...overrides,
  } as TraceSpan;
}

const validStep = {
  iteration: 2,
  max_iterations: 3,
  runner: 'pytest',
  test_selected: ['tests/test_x.py'],
  command: 'pytest tests/test_x.py',
  exit_code: 1,
  stdout_tail: 'FAIL',
  stderr_tail: '',
  duration_ms: 1234,
  verdict: 'fail',
  files_edited_since_last_verify: ['src/x.py'],
};

describe('VerifyStepCard', () => {
  it('renders iteration counter, runner, and verdict when result is present', () => {
    const span = makeSpan({ result: validStep });
    render(<VerifyStepCard span={span} />);

    expect(screen.getByText(/iteration 2 \/ 3/)).toBeInTheDocument();
    expect(screen.getByText('pytest')).toBeInTheDocument();
    expect(screen.getByText('FAIL', { selector: '.verdictBadge, [data-verdict]' })).toBeInTheDocument();
  });

  it('reads step from attributes.observation as fallback', () => {
    const span = makeSpan({ observation: validStep });
    render(<VerifyStepCard span={span} />);
    expect(screen.getByText(/iteration 2 \/ 3/)).toBeInTheDocument();
  });

  it('reads step from the span attributes root as last-resort', () => {
    const span = makeSpan(validStep as unknown as Record<string, unknown>);
    render(<VerifyStepCard span={span} />);
    expect(screen.getByText(/iteration 2 \/ 3/)).toBeInTheDocument();
  });

  it('renders empty-state card when no VerificationStep payload can be parsed', () => {
    const span = makeSpan({ irrelevant: 'garbage' });
    render(<VerifyStepCard span={span} />);
    expect(screen.getByTestId('verify-step-card-empty')).toBeInTheDocument();
  });

  it('renders the command in a <code> block', () => {
    const span = makeSpan({ result: validStep });
    const { container } = render(<VerifyStepCard span={span} />);
    const code = container.querySelector('code');
    expect(code?.textContent).toContain('pytest');
  });

  it('renders stdout tail only if non-empty', () => {
    const span = makeSpan({ result: { ...validStep, stdout_tail: '' } });
    render(<VerifyStepCard span={span} />);
    expect(screen.queryByText(/stdout tail/i)).not.toBeInTheDocument();
  });

  it('applies the correct verdict class for pass', () => {
    const span = makeSpan({
      result: { ...validStep, verdict: 'pass' },
    });
    const { container } = render(<VerifyStepCard span={span} />);
    const badge = container.querySelector('[data-verdict="pass"]');
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe('PASS');
  });
});
