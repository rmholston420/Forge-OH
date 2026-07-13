import type { Meta, StoryObj } from '@storybook/react';
import { StatusBadge } from './StatusBadge';
import type { StatusBadgeStatus } from './StatusBadge';

const meta: Meta<typeof StatusBadge> = {
  title: 'Core/StatusBadge',
  component: StatusBadge,
  parameters: { layout: 'centered' },
  argTypes: {
    status: {
      control: 'select',
      options: [
        'idle', 'running', 'streaming', 'queued', 'paused',
        'awaiting_approval', 'succeeded', 'failed', 'blocked',
      ] satisfies StatusBadgeStatus[],
    },
    size: { control: 'radio', options: ['sm', 'md'] },
    dot: { control: 'boolean' },
  },
};
export default meta;

type Story = StoryObj<typeof StatusBadge>;

export const Running: Story = { args: { status: 'running' } };
export const Streaming: Story = { args: { status: 'streaming' } };
export const AwaitingApproval: Story = { args: { status: 'awaiting_approval' } };
export const Succeeded: Story = { args: { status: 'succeeded' } };
export const Failed: Story = { args: { status: 'failed' } };
export const Paused: Story = { args: { status: 'paused' } };
export const Blocked: Story = { args: { status: 'blocked' } };
export const Queued: Story = { args: { status: 'queued' } };
export const Idle: Story = { args: { status: 'idle' } };

export const AllStatuses: Story = {
  render: () => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '16px' }}>
      {(['idle','running','streaming','queued','paused','awaiting_approval','succeeded','failed','blocked'] as StatusBadgeStatus[]).map((s) => (
        <StatusBadge key={s} status={s} />
      ))}
    </div>
  ),
};

export const AllStatusesSmall: Story = {
  render: () => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '16px' }}>
      {(['idle','running','streaming','queued','paused','awaiting_approval','succeeded','failed','blocked'] as StatusBadgeStatus[]).map((s) => (
        <StatusBadge key={s} status={s} size="sm" />
      ))}
    </div>
  ),
};
