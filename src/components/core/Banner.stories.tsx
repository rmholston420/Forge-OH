import type { Meta, StoryObj } from '@storybook/react';
import { Banner } from './Banner';

const meta: Meta<typeof Banner> = {
  title: 'Core/Banner',
  component: Banner,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
};
export default meta;
type Story = StoryObj<typeof Banner>;

export const Info: Story = { args: { variant: 'info', children: 'This is an informational banner.' } };
export const Success: Story = { args: { variant: 'success', children: 'Action completed successfully.' } };
export const Warning: Story = { args: { variant: 'warning', children: 'Awaiting your approval before continuing.' } };
export const Error: Story = { args: { variant: 'error', children: 'Run failed: agent exceeded loop threshold.' } };
export const Streaming: Story = { args: { variant: 'streaming', children: 'Agent is streaming — events arriving live.' } };
export const Dismissible: Story = { args: { variant: 'warning', dismissible: true, children: 'You can dismiss this banner.' } };
