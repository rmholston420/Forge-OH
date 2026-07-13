import type { Meta, StoryObj } from '@storybook/react';
import { EmptyState } from './EmptyState';

const meta: Meta<typeof EmptyState> = {
  title: 'Core/EmptyState',
  component: EmptyState,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof EmptyState>;

export const NoRuns: Story = {
  args: {
    icon: 'play-circle',
    heading: 'No runs yet',
    description: 'Launch a run to start supervising an agent.',
    action: { label: 'New Run', onClick: () => {} },
  },
};

export const NoWorkspaces: Story = {
  args: {
    icon: 'box',
    heading: 'No workspaces',
    description: 'Create a workspace before launching a run.',
    action: { label: 'Add Workspace', onClick: () => {} },
  },
};

export const NoArtifacts: Story = {
  args: {
    icon: 'file',
    heading: 'No artifacts',
    description: 'Artifacts will appear here once the agent produces output.',
  },
};

export const ErrorState: Story = {
  args: {
    icon: 'alert-circle',
    heading: 'Something went wrong',
    description: 'Failed to load data. Please try again.',
    action: { label: 'Retry', onClick: () => {} },
    variant: 'error',
  },
};
