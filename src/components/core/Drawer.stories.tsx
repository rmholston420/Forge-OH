import type { Meta, StoryObj } from '@storybook/react';
import { Drawer } from './Drawer';

const meta: Meta<typeof Drawer> = {
  title: 'Core/Drawer',
  component: Drawer,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj<typeof Drawer>;

export const RightPanel: Story = {
  args: {
    open: true,
    side: 'right',
    title: 'Workspace Details',
    children: <div style={{ padding: 24 }}>Drawer content goes here.</div>,
  },
};

export const LeftPanel: Story = {
  args: {
    open: true,
    side: 'left',
    title: 'Inspector',
    children: <div style={{ padding: 24 }}>Inspector content.</div>,
  },
};

export const Closed: Story = {
  args: {
    open: false,
    side: 'right',
    title: 'Hidden Drawer',
    children: null,
  },
};
