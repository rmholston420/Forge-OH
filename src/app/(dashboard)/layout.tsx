'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/navigation/Sidebar';
import { Topbar } from '@/components/navigation/Topbar';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { useAppStore } from '@/lib/state/app-store';
import styles from './dashboard.module.css';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  const sidebarExpanded = useAppStore((s) => s.sidebarExpanded);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const commandPaletteOpen = useAppStore((s) => s.commandPaletteOpen);
  const toggleCommandPalette = useAppStore((s) => s.toggleCommandPalette);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggleCommandPalette]);

  return (
    <AuthGuard>
      <div className={styles.shell}>
        <Sidebar collapsed={!sidebarExpanded} onToggle={toggleSidebar} />
        <Topbar onCommandPaletteOpen={() => setCommandPaletteOpen(true)} />
        <main
          className={[styles.content, !sidebarExpanded ? styles['content--collapsed'] : ''].join(' ')}
          id="main-content"
        >
          {children}
        </main>
        <CommandPalette
          open={commandPaletteOpen}
          onClose={() => setCommandPaletteOpen(false)}
          commands={[
            { id: 'goto-runs', label: 'Go to Runs', action: () => router.push('/runs') },
            { id: 'goto-workspaces', label: 'Go to Workspaces', action: () => router.push('/workspaces') },
            { id: 'goto-settings', label: 'Go to Settings', action: () => router.push('/settings') },
          ]}
        />
      </div>
    </AuthGuard>
  );
}
