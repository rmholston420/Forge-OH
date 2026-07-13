'use client';
import React, { useEffect, useRef } from 'react';
import type { TerminalCommand } from '@/lib/schemas/terminal';
import styles from './TerminalEmulator.module.css';

// xterm.js is dynamically imported to avoid SSR issues
async function loadXterm() {
  const [{ Terminal }, { FitAddon }] = await Promise.all([
    import('@xterm/xterm'),
    import('@xterm/addon-fit'),
  ]);
  return { Terminal, FitAddon };
}

export interface TerminalEmulatorProps {
  /** Historiccommands to replay on mount. */
  commands?: TerminalCommand[];
  /** When true, renders a live input line at the bottom. */
  interactive?: boolean;
  /** Unique key: when changed, terminal is re-created. */
  sessionKey?: string;
}

export const TerminalEmulator: React.FC<TerminalEmulatorProps> = ({
  commands = [],
  interactive = false,
  sessionKey = 'default',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let destroyed = false;

    loadXterm().then(({ Terminal, FitAddon }) => {
      if (destroyed || !containerRef.current) return;

      const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
        (document.documentElement.getAttribute('data-theme') === null &&
          window.matchMedia('(prefers-color-scheme: dark)').matches);

      const THEME_DARK = {
        background: '#171614',
        foreground: '#cdccca',
        cursor: '#4f98a3',
        cursorAccent: '#171614',
        selectionBackground: 'rgba(79,152,163,0.25)',
        black:   '#1c1b19', red:     '#dd6974', green:  '#6daa45', yellow: '#e8af34',
        blue:    '#5591c7', magenta: '#a86fdf', cyan:   '#4f98a3', white:  '#cdccca',
        brightBlack:   '#393836', brightRed:     '#f0616b', brightGreen:  '#35c47c',
        brightYellow:  '#fdc551', brightBlue:    '#5c93f3', brightMagenta: '#c97cff',
        brightCyan:    '#4fb3c2', brightWhite:   '#f0f0f0',
      };

      const THEME_LIGHT = {
        background: '#f7f6f2',
        foreground: '#28251d',
        cursor: '#01696f',
        cursorAccent: '#f7f6f2',
        selectionBackground: 'rgba(1,105,111,0.15)',
        black:   '#28251d', red:     '#a13544', green:  '#437a22', yellow: '#d19900',
        blue:    '#006494', magenta: '#7a39bb', cyan:   '#01696f', white:  '#f7f6f2',
        brightBlack:   '#7a7974', brightRed:     '#cc3d4e', brightGreen:  '#559e30',
        brightYellow:  '#f0ad00', brightBlue:    '#2880b8', brightMagenta: '#9950e0',
        brightCyan:    '#1a8b93', brightWhite:   '#fbfbf9',
      };

      const term = new Terminal({
        theme: isDark ? THEME_DARK : THEME_LIGHT,
        fontFamily: 'var(--font-mono, "Menlo", "Monaco", monospace)',
        fontSize: 13,
        lineHeight: 1.5,
        cursorBlink: interactive,
        cursorStyle: 'bar',
        scrollback: 5000,
        disableStdin: !interactive,
      });

      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(containerRef.current!);
      fitAddon.fit();

      // Render history
      for (const cmd of commands) {
        const exitColor = cmd.exitCode === 0 ? '\x1b[32m' : '\x1b[31m';
        term.writeln(`\x1b[1;36m$\x1b[0m \x1b[1m${cmd.command}\x1b[0m`);
        if (cmd.output) {
          term.write(cmd.output);
          if (!cmd.output.endsWith('\n')) term.writeln('');
        }
        if (cmd.exitCode !== null) {
          term.writeln(`${exitColor}[exit ${cmd.exitCode}]\x1b[0m`);
        }
        term.writeln('');
      }

      if (commands.length === 0) {
        term.writeln('\x1b[2mNo commands executed yet.\x1b[0m');
      }

      if (interactive) {
        term.writeln('');
        term.write('\x1b[1;36m$\x1b[0m ');
      }

      const resizeObserver = new ResizeObserver(() => fitAddon.fit());
      resizeObserver.observe(containerRef.current!);

      termRef.current = { term, resizeObserver };
    });

    return () => {
      destroyed = true;
      termRef.current?.resizeObserver.disconnect();
      termRef.current?.term.dispose();
      termRef.current = null;
    };
  }, [sessionKey]);

  // Append new commands incrementally when the commands array grows
  useEffect(() => {
    const { term } = termRef.current ?? {};
    if (!term || commands.length === 0) return;
    const last = commands[commands.length - 1];
    const exitColor = last.exitCode === 0 ? '\x1b[32m' : '\x1b[31m';
    term.writeln(`\x1b[1;36m$\x1b[0m \x1b[1m${last.command}\x1b[0m`);
    if (last.output) {
      term.write(last.output);
      if (!last.output.endsWith('\n')) term.writeln('');
    }
    if (last.exitCode !== null) {
      term.writeln(`${exitColor}[exit ${last.exitCode}]\x1b[0m`);
    }
    term.writeln('');
  }, [commands.length]);

  return (
    <div
      ref={containerRef}
      className={styles.container}
      role="region"
      aria-label="Agent terminal output"
    />
  );
};
