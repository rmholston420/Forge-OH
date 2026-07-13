import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta = {
  title: 'Core/Button',
  component: Button,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'tertiary', 'destructive'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
    loading: { control: 'boolean' },
    disabled: { control: 'boolean' },
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = { args: { children: 'New Run', variant: 'primary' } };
export const Secondary: Story = { args: { children: 'Cancel', variant: 'secondary' } };
export const Tertiary: Story = { args: { children: 'Settings', variant: 'tertiary' } };
export const Destructive: Story = { args: { children: 'Delete Run', variant: 'destructive' } };
export const Loading: Story = { args: { children: 'Saving...', loading: true } };
export const Disabled: Story = { args: { children: 'New Run', disabled: true } };
export const Small: Story = { args: { children: 'Sm', size: 'sm' } };
export const Large: Story = { args: { children: 'Launch Agent', size: 'lg' } };
