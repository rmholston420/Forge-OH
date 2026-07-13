import type { Meta, StoryObj } from '@storybook/react';
import { Badge, StatusBadge } from './Badge';

const meta = {
  title: 'Core/Badge',
  component: Badge,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
} satisfies Meta<typeof Badge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Success: Story = { args: { variant: 'success', children: 'succeeded' } };
export const Warning: Story = { args: { variant: 'warning', children: 'awaiting approval' } };
export const Error: Story = { args: { variant: 'error', children: 'failed' } };
export const Running: Story = { args: { variant: 'running', children: 'running' } };
export const Paused: Story = { args: { variant: 'paused', children: 'paused' } };
export const AllStatuses: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      {['idle','running','streaming','queued','paused','awaiting_approval','succeeded','failed','blocked'].map(
        (s) => <StatusBadge key={s} status={s} />
      )}
    </div>
  ),
};
