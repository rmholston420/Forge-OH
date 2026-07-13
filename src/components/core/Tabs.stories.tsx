import type { Meta, StoryObj } from '@storybook/react';
import { Tabs } from './Tabs';

const meta: Meta<typeof Tabs> = {
  title: 'Core/Tabs',
  component: Tabs,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
};
export default meta;
type Story = StoryObj<typeof Tabs>;

const runDetailTabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'files', label: 'Files' },
  { id: 'terminal', label: 'Terminal' },
  { id: 'browser', label: 'Browser' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'security', label: 'Security' },
];

export const Underline: Story = {
  args: {
    variant: 'underline',
    tabs: runDetailTabs,
    activeTab: 'overview',
    onTabChange: () => {},
  },
};

export const Pill: Story = {
  args: {
    variant: 'pill',
    tabs: runDetailTabs.slice(0, 4),
    activeTab: 'files',
    onTabChange: () => {},
  },
};

export const Segmented: Story = {
  args: {
    variant: 'segmented',
    tabs: [
      { id: 'split', label: 'Split' },
      { id: 'unified', label: 'Unified' },
    ],
    activeTab: 'split',
    onTabChange: () => {},
  },
};

export const WithBadges: Story = {
  args: {
    variant: 'underline',
    tabs: [
      { id: 'overview', label: 'Overview' },
      { id: 'files', label: 'Files', badge: 12 },
      { id: 'terminal', label: 'Terminal' },
    ],
    activeTab: 'overview',
    onTabChange: () => {},
  },
};
