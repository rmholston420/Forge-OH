import { render, screen } from '@testing-library/react';
import { VerifyIterationsWidget } from '@/components/domain/VerifyIterationsWidget';
import type { TraceSpan } from '@/lib/schemas/trace';

function verifySpan(
  iteration: number,
  verdict: string,
  max_iterations = 3,
): TraceSpan {
  return {
    spanId: `s-${iteration}`,
    traceId: 't',
    parentSpanId: null,
    name: 'verify_step',
    kind: 'verify',
    startTime: new Date().toISOString(),
    endTime: null,
    durationMs: null,
    status: verdict === 'pass' ? 'ok' : 'error',
    attributes: {
      result: {
        iteration,
        max_iterations,
        runner: 'pytest',
        test_selected: [],
        command: '',
        exit_code: verdict === 'pass' ? 0 : 1,
        stdout_tail: '',
        stderr_tail: '',
        duration_ms: 100,
        verdict,
        files_edited_since_last_verify: [],
      },
    },
    children: [],
  } as TraceSpan;
}

function nonVerifySpan(): TraceSpan {
  return {
    spanId: 'x',
    traceId: 't',
    parentSpanId: null,
    name: 'llm.call',
    kind: 'llm',
    startTime: new Date().toISOString(),
    endTime: null,
    durationMs: null,
    status: 'ok',
    attributes: {},
    children: [],
  } as TraceSpan;
}

describe('VerifyIterationsWidget', () => {
  it('renders empty-state when no verify spans are present', () => {
    render(<VerifyIterationsWidget spans={[nonVerifySpan()]} />);
    expect(screen.getByTestId('verify-iterations-empty')).toBeInTheDocument();
    expect(screen.getByText(/No verify steps/i)).toBeInTheDocument();
  });

  it('renders max iteration / cap and last verdict', () => {
    const spans = [
      nonVerifySpan(),
      verifySpan(1, 'fail'),
      verifySpan(2, 'pass'),
    ];
    const { container } = render(<VerifyIterationsWidget spans={spans} />);
    // usedIter=2 rendered as the big top-line number inside .big
    const big = container.querySelector('.big, [class*="big"]');
    expect(big?.textContent).toContain('2');
    expect(screen.getByText(/\/ 3/)).toBeInTheDocument();
    // Latest verdict is pass
    expect(screen.getByText('pass')).toBeInTheDocument();
  });

  it('sorts chips by iteration ascending', () => {
    const spans = [verifySpan(3, 'pass'), verifySpan(1, 'fail'), verifySpan(2, 'fail')];
    render(<VerifyIterationsWidget spans={spans} />);
    const chips = screen.getAllByTitle(/iteration \d: /);
    expect(chips.map((c) => c.textContent)).toEqual(['1', '2', '3']);
  });

  it('skips spans that fail schema parsing', () => {
    const bad: TraceSpan = {
      ...verifySpan(1, 'pass'),
      attributes: { result: { iteration: 'not-a-number' } },
    };
    render(<VerifyIterationsWidget spans={[bad]} />);
    // Falls through to empty-state because nothing parsed.
    expect(screen.getByTestId('verify-iterations-empty')).toBeInTheDocument();
  });

  it('reads max_iterations from the highest iteration span', () => {
    const spans = [verifySpan(1, 'fail', 5), verifySpan(2, 'fail', 5)];
    render(<VerifyIterationsWidget spans={spans} />);
    expect(screen.getByText(/\/ 5/)).toBeInTheDocument();
  });
});
