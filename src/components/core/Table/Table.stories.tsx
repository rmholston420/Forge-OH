import type { Meta, StoryObj } from '@storybook/react';
import { Table } from './Table';

const meta: Meta<typeof Table> = {
  title: 'Core/Table',
  component: Table,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof Table>;

interface SampleRow {
  id: string;
  name: string;
  status: string;
  updatedAt: string;
}

const sampleRows: SampleRow[] = [
  { id: '1', name: 'Refactor auth middleware', status: 'Running', updatedAt: '2 min ago' },
  { id: '2', name: 'Add Zod validation', status: 'Awaiting Approval', updatedAt: '5 min ago' },
  { id: '3', name: 'Write unit tests', status: 'Succeeded', updatedAt: '45 min ago' },
];

const columns = [
  { key: 'name' as const, header: 'Name' },
  { key: 'status' as const, header: 'Status' },
  { key: 'updatedAt' as const, header: 'Updated', align: 'right' as const },
];

export const Default: Story = {
  args: {
    columns,
    rows: sampleRows,
    getRowKey: (row) => row.id,
    'aria-label': 'Sample table',
  },
};

export const WithRowClick: Story = {
  args: {
    ...Default.args,
    onRowClick: (row) => alert(`Clicked: ${row.name}`),
  },
};

export const WithSelection: Story = {
  args: {
    ...Default.args,
    onRowClick: (row) => alert(`Clicked: ${row.name}`),
    selectedRowKey: '2',
  },
};

export const Loading: Story = {
  args: {
    ...Default.args,
    loading: true,
  },
};

export const Empty: Story = {
  args: {
    ...Default.args,
    rows: [],
    emptyState: <span style={{ color: 'var(--color-text-muted)' }}>No runs found. Start a new run to get going.</span>,
  },
};
