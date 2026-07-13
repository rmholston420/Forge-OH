import type { Meta, StoryObj } from '@storybook/nextjs';
import { StatusBadge } from './StatusBadge';
import type { RunStatus } from '@/lib/schemas/run';

const ALL_STATUSES: RunStatus[] = [
  'idle', 'running', 'streaming', 'queued', 'paused',
  'awaiting_approval', 'succeeded', 'failed', 'blocked',
];

const meta: Meta<typeof StatusBadge> = {
  title: 'Core/StatusBadge',
  component: StatusBadge,
  parameters: { layout: 'centered' },
  args: { showDot: false },
};

export default meta;
type Story = StoryObj<typeof StatusBadge>;

export const AllStates: Story = {
  render: () => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '16px' }}>
      {ALL_STATUSES.map((s) => (
        <StatusBadge key={s} status={s} showDot />
      ))}
    </div>
  ),
};

export const Running: Story = { args: { status: 'running', showDot: true } };
export const AwaitingApproval: Story = { args: { status: 'awaiting_approval', showDot: false } };
export const Succeeded: Story = { args: { status: 'succeeded' } };
export const Failed: Story = { args: { status: 'failed' } };
export const Idle: Story = { args: { status: 'idle' } };
