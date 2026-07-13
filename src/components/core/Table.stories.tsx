import type { Meta, StoryObj } from '@storybook/nextjs';
import { Table } from './Table';

interface SampleRow {
  id: string;
  name: string;
  status: string;
  created: string;
}

const sampleRows: SampleRow[] = [
  { id: '1', name: 'Run alpha', status: 'succeeded', created: '2026-07-13' },
  { id: '2', name: 'Run beta', status: 'running', created: '2026-07-13' },
  { id: '3', name: 'Run gamma', status: 'failed', created: '2026-07-12' },
];

const sampleColumns = [
  { key: 'name', header: 'Name', render: (r: SampleRow) => r.name },
  { key: 'status', header: 'Status', render: (r: SampleRow) => r.status },
  { key: 'created', header: 'Created', render: (r: SampleRow) => r.created, align: 'right' as const },
];

const meta: Meta<typeof Table> = {
  title: 'Core/Table',
  component: Table,
  parameters: { layout: 'padded' },
};

export default meta;
type Story = StoryObj<typeof Table>;

export const Default: Story = {
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    getRowKey: (r) => r.id,
  },
};

export const Loading: Story = {
  args: {
    columns: sampleColumns,
    rows: [],
    getRowKey: (r) => r.id,
    loading: true,
    loadingRowCount: 4,
  },
};

export const Empty: Story = {
  args: {
    columns: sampleColumns,
    rows: [],
    getRowKey: (r) => r.id,
    emptyState: <span style={{ color: 'var(--color-text-muted)' }}>No runs yet. Create one to get started.</span>,
  },
};

export const Clickable: Story = {
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    getRowKey: (r) => r.id,
    onRowClick: (r) => alert(`Clicked: ${r.name}`),
  },
};
