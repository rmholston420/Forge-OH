import type { Meta, StoryObj } from '@storybook/react';
import { Input } from './Input';

const meta: Meta<typeof Input> = {
  title: 'Core/Input',
  component: Input,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Text: Story = { args: { type: 'text', placeholder: 'Enter task prompt…', label: 'Task' } };
export const Search: Story = { args: { type: 'search', placeholder: 'Search runs…' } };
export const Path: Story = { args: { type: 'text', placeholder: '/workspace/project', label: 'Workspace path' } };
export const Secret: Story = { args: { type: 'password', placeholder: '••••••••', label: 'API Key' } };
export const Disabled: Story = { args: { type: 'text', placeholder: 'Disabled input', label: 'Disabled', disabled: true } };
export const Error: Story = { args: { type: 'text', placeholder: 'Invalid value', label: 'Run title', error: 'Title is required' } };
export const Loading: Story = { args: { type: 'text', placeholder: 'Loading…', label: 'Workspace', loading: true } };
