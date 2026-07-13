import { render, screen } from '@testing-library/react';
import { KpiCard } from '@/features/metrics/KpiCard';

describe('KpiCard', () => {
  it('renders label and value', () => {
    render(<KpiCard label="Total runs" value={42} />);
    expect(screen.getByText('Total runs')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows up arrow for positive delta', () => {
    render(<KpiCard label="Cost" value="$4.20" delta={12.5} />);
    expect(screen.getByText(/12.5%/)).toBeInTheDocument();
    expect(screen.getByText(/↑/)).toBeInTheDocument();
  });

  it('shows down arrow for negative delta', () => {
    render(<KpiCard label="Cost" value="$2.10" delta={-8.3} />);
    expect(screen.getByText(/↓/)).toBeInTheDocument();
  });

  it('renders sparkline when sparkData provided', () => {
    const data = [1,2,3,4,5,6,7].map(v => ({ value: v }));
    const { container } = render(<KpiCard label="Runs" value={7} sparkData={data} />);
    expect(container.querySelector('svg.sparkline')).toBeInTheDocument();
  });
});
