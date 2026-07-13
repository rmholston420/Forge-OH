import type { Meta, StoryObj } from '@storybook/react';
import { Modal } from './Modal';

const meta: Meta<typeof Modal> = {
  title: 'Core/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof Modal>;

export const Default: Story = {
  args: {
    open: true,
    title: 'New Run',
    children: <div style={{ padding: '0 0 16px' }}>Configure your run settings here.</div>,
    onClose: () => {},
  },
};

export const Destructive: Story = {
  args: {
    open: true,
    title: 'Delete Secret',
    children: <p>This action cannot be undone. The secret will be permanently removed.</p>,
    onClose: () => {},
    variant: 'destructive',
    primaryAction: { label: 'Delete', onClick: () => {} },
    secondaryAction: { label: 'Cancel', onClick: () => {} },
  },
};

export const WithActions: Story = {
  args: {
    open: true,
    title: 'Approve Action',
    children: <p>The agent is requesting permission to run a shell command.</p>,
    onClose: () => {},
    primaryAction: { label: 'Approve', onClick: () => {} },
    secondaryAction: { label: 'Reject', onClick: () => {} },
  },
};
