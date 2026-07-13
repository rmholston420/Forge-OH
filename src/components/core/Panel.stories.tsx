import type { Meta, StoryObj } from '@storybook/react';
import { Panel } from './Panel';

const meta: Meta<typeof Panel> = {
  title: 'Core/Panel',
  component: Panel,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
};
export default meta;
type Story = StoryObj<typeof Panel>;

export const Default: Story = {
  args: {
    title: 'Run Details',
    children: <div>Panel content goes here.</div>,
  },
};

export const Collapsible: Story = {
  args: {
    title: 'Environment Variables',
    collapsible: true,
    defaultCollapsed: false,
    children: <div>Collapsible panel content.</div>,
  },
};

export const DefaultCollapsed: Story = {
  args: {
    title: 'Advanced Settings',
    collapsible: true,
    defaultCollapsed: true,
    children: <div>This content starts collapsed.</div>,
  },
};

export const Loading: Story = {
  args: {
    title: 'Artifacts',
    loading: true,
    children: null,
  },
};
