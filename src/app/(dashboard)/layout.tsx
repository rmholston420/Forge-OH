'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { Topbar } from '@/components/navigation/Topbar';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import styles from './dashboard.module.css';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className={styles.shell}>
      <Sidebar collapsed={sidebarCollapsed} onToggle={setSidebarCollapsed} />
      <Topbar onCommandPaletteOpen={() => setCmdOpen(true)} />
      <main
        className={[styles.content, sidebarCollapsed ? styles['content--collapsed'] : ''].join(' ')}
        id="main-content"
      >
        {children}
      </main>
      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        commands={[
          { id: 'goto-runs', label: 'Go to Runs', action: () => window.location.assign('/runs') },
          { id: 'goto-workspaces', label: 'Go to Workspaces', action: () => window.location.assign('/workspaces') },
          { id: 'goto-settings', label: 'Go to Settings', action: () => window.location.assign('/settings') },
        ]}
      />
    </div>
  );
}
