import type { Meta, StoryObj } from '@storybook/react';
import { Skeleton, SkeletonText } from './Skeleton';

const meta = {
  title: 'Core/Skeleton',
  component: Skeleton,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
} satisfies Meta<typeof Skeleton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { args: { width: 200, height: 16 } };
export const Text: Story = { render: () => <SkeletonText lines={3} /> };
export const Card: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: 360, padding: 16, background: 'var(--color-bg-surface)', borderRadius: 8 }}>
      <Skeleton width="60%" height={16} />
      <SkeletonText lines={2} />
      <Skeleton width={80} height={28} borderRadius="6px" />
    </div>
  ),
};
