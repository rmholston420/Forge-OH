/**
 * src/tests/unit/domain-ApprovalBanner.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApprovalBanner } from '@/components/domain/ApprovalBanner';

const base = { onApprove: vi.fn(), onReject: vi.fn() };

describe('ApprovalBanner', () => {
  it('renders role=alert with aria-live=assertive', () => {
    render(<ApprovalBanner {...base} />);
    const el = screen.getByRole('alert');
    expect(el).toHaveAttribute('aria-live', 'assertive');
  });

  it('renders Approve and Reject buttons', () => {
    render(<ApprovalBanner {...base} />);
    expect(screen.getByLabelText('Approve agent action')).toBeInTheDocument();
    expect(screen.getByLabelText('Reject agent action')).toBeInTheDocument();
  });

  it('calls onApprove when Approve is clicked', async () => {
    const onApprove = vi.fn();
    render(<ApprovalBanner {...base} onApprove={onApprove} />);
    await userEvent.click(screen.getByLabelText('Approve agent action'));
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it('calls onReject when Reject is clicked', async () => {
    const onReject = vi.fn();
    render(<ApprovalBanner {...base} onReject={onReject} />);
    await userEvent.click(screen.getByLabelText('Reject agent action'));
    expect(onReject).toHaveBeenCalledOnce();
  });

  it('loading=true disables both buttons', () => {
    render(<ApprovalBanner {...base} loading />);
    expect(screen.getByLabelText('Approve agent action')).toBeDisabled();
    expect(screen.getByLabelText('Reject agent action')).toBeDisabled();
  });

  it('renders context string when provided', () => {
    render(<ApprovalBanner {...base} context="Run shell command: rm -rf /tmp" />);
    expect(screen.getByText('Run shell command: rm -rf /tmp')).toBeInTheDocument();
  });

  it('does not render context element when omitted', () => {
    const { container } = render(<ApprovalBanner {...base} />);
    // context span would contain that specific text; its absence means no context element
    expect(container.querySelectorAll('[class*="context"]')).toHaveLength(0);
  });
});
