import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DiffViewer } from '@/components/domain/DiffViewer';

// Monaco editor is heavy; mock the dynamic import
vi.mock('monaco-editor', () => ({
  editor: {
    defineTheme: vi.fn(),
    createDiffEditor: vi.fn(() => ({
      setModel: vi.fn(),
      dispose: vi.fn(),
    })),
    createModel: vi.fn(),
  },
}));

describe('DiffViewer', () => {
  it('renders container for non-binary diff', () => {
    const diff = {
      path: 'src/foo.ts', status: 'modified' as const,
      additions: 3, deletions: 1,
      original: 'const a = 1;', modified: 'const a = 2;',
      language: 'typescript', isBinary: false,
    };
    render(<DiffViewer diff={diff} />);
    expect(screen.getByLabelText(`Diff for ${diff.path}`)).toBeTruthy();
  });

  it('renders binary placeholder for binary files', () => {
    const diff = {
      path: 'logo.png', status: 'added' as const,
      additions: 0, deletions: 0,
      original: null, modified: null,
      language: 'plaintext', isBinary: true,
    };
    render(<DiffViewer diff={diff} />);
    expect(screen.getByText(/Binary file/)).toBeTruthy();
  });
});
