import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ArtifactCard } from '@/components/domain/ArtifactCard';

const mockArtifact = {
  id: 'art-1',
  runId: 'run-1',
  type: 'file' as const,
  name: 'output.txt',
  mimeType: 'text/plain',
  sizeBytes: 1024,
  url: 'https://example.com/output.txt',
  previewUrl: null,
  createdAt: '2026-07-12T00:00:00Z',
};

describe('ArtifactCard', () => {
  it('renders artifact name', () => {
    render(<ArtifactCard artifact={mockArtifact} />);
    expect(screen.getByText('output.txt')).toBeTruthy();
  });

  it('renders download link', () => {
    render(<ArtifactCard artifact={mockArtifact} />);
    const link = screen.getByRole('link', { name: /Download/ });
    expect(link.getAttribute('href')).toBe(mockArtifact.url);
  });

  it('does not render preview button for non-previewable types', () => {
    render(<ArtifactCard artifact={mockArtifact} />);
    expect(screen.queryByRole('button', { name: /Preview/ })).toBeNull();
  });

  it('calls onPreview for screenshot type', () => {
    const onPreview = vi.fn();
    const screenshotArtifact = {
      ...mockArtifact, type: 'screenshot' as const,
      previewUrl: 'https://example.com/thumb.png',
    };
    render(<ArtifactCard artifact={screenshotArtifact} onPreview={onPreview} />);
    const previewBtn = screen.getAllByLabelText(/Preview/);
    fireEvent.click(previewBtn[0]);
    expect(onPreview).toHaveBeenCalledWith('art-1');
  });
});
