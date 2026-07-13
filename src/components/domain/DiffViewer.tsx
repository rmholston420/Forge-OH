'use client';
import React, { useEffect, useRef } from 'react';
import type { FileDiff } from '@/lib/schemas/file-diff';
import styles from './DiffViewer.module.css';

// Monaco is loaded dynamically to avoid SSR issues
let monacoLoaded = false;
let monacoInstance: any = null;

async function loadMonaco() {
  if (monacoLoaded) return monacoInstance;
  const monaco = await import('monaco-editor');
  monacoLoaded = true;
  monacoInstance = monaco;
  return monaco;
}

export interface DiffViewerProps {
  diff: FileDiff;
  mode?: 'split' | 'unified';
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ diff, mode = 'split' }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || diff.isBinary) return;
    let destroyed = false;

    loadMonaco().then((monaco) => {
      if (destroyed || !containerRef.current) return;

      const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
        (document.documentElement.getAttribute('data-theme') === null &&
          window.matchMedia('(prefers-color-scheme: dark)').matches);

      monaco.editor.defineTheme('forge-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [],
        colors: {
          'editor.background': '#171D29',
          'diffEditor.insertedTextBackground': '#1e3a2a',
          'diffEditor.removedTextBackground': '#3a1e1e',
        },
      });
      monaco.editor.defineTheme('forge-light', {
        base: 'vs',
        inherit: true,
        rules: [],
        colors: {
          'editor.background': '#F7F6F2',
        },
      });

      const editor = monaco.editor.createDiffEditor(containerRef.current!, {
        theme: isDark ? 'forge-dark' : 'forge-light',
        renderSideBySide: mode === 'split',
        readOnly: true,
        scrollBeyondLastLine: false,
        fontSize: 13,
        fontFamily: 'var(--font-mono)',
        minimap: { enabled: false },
        diffAlgorithm: 'advanced',
        renderOverviewRuler: false,
        scrollbar: { vertical: 'visible', horizontal: 'auto' },
      });

      editor.setModel({
        original: monaco.editor.createModel(
          diff.original ?? '',
          diff.language,
        ),
        modified: monaco.editor.createModel(
          diff.modified ?? '',
          diff.language,
        ),
      });

      editorRef.current = editor;
    });

    return () => {
      destroyed = true;
      editorRef.current?.dispose();
      editorRef.current = null;
    };
  }, [diff.path, mode]);

  if (diff.isBinary) {
    return (
      <div className={styles.binaryPlaceholder}>
        <span className={styles.binaryIcon} aria-hidden="true">📎</span>
        <span>Binary file — no diff available</span>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={styles.container} aria-label={`Diff for ${diff.path}`} />
  );
};
