/**
 * src/tests/unit/core-Tabs.test.tsx
 * Covers: Tabs component
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs } from '@/components/core/Tabs';

const tabs = [
  { id: 'plan', label: 'Plan' },
  { id: 'events', label: 'Events' },
  { id: 'artifacts', label: 'Artifacts', disabled: true },
];

describe('Tabs', () => {
  it('renders all tab labels', () => {
    render(<Tabs tabs={tabs} activeTab="plan" onTabChange={() => {}} />);
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Events')).toBeInTheDocument();
    expect(screen.getByText('Artifacts')).toBeInTheDocument();
  });

  it('calls onTabChange with correct id when tab is clicked', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} activeTab="plan" onTabChange={onChange} />);
    await userEvent.click(screen.getByText('Events'));
    expect(onChange).toHaveBeenCalledWith('events');
  });

  it('does not call onTabChange when disabled tab is clicked', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} activeTab="plan" onTabChange={onChange} />);
    const artifactsBtn = screen.getByText('Artifacts').closest('button')!;
    expect(artifactsBtn).toBeDisabled();
    await userEvent.click(artifactsBtn);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('active tab has distinguishing class', () => {
    render(<Tabs tabs={tabs} activeTab="events" onTabChange={() => {}} />);
    const eventsBtn = screen.getByText('Events').closest('button')!;
    // active class could be 'active', 'tab--active', etc.
    expect(eventsBtn.className).toMatch(/active/);
  });

  it('inactive tab does not have active class', () => {
    render(<Tabs tabs={tabs} activeTab="events" onTabChange={() => {}} />);
    const planBtn = screen.getByText('Plan').closest('button')!;
    expect(planBtn.className).not.toMatch(/tab--active$/);
  });

  it.each(['underline','pill','segmented'])('variant=%s renders without throw', (variant) => {
    expect(() =>
      render(<Tabs tabs={tabs} activeTab="plan" onTabChange={() => {}} variant={variant as any} />)
    ).not.toThrow();
  });

  it('renders correct number of buttons', () => {
    render(<Tabs tabs={tabs} activeTab="plan" onTabChange={() => {}} />);
    expect(screen.getAllByRole('button')).toHaveLength(tabs.length);
  });
});
