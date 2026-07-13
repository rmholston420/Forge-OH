import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { href: '/runs',          label: 'Runs',          icon: '▶' },
  { href: '/agents',        label: 'Agents',         icon: '🤖' },
  { href: '/workspaces',    label: 'Workspaces',     icon: '📦' },
  { href: '/tools-mcp',     label: 'Tools & MCP',   icon: '🔧' },
  { href: '/plugins',       label: 'Plugins',        icon: '🧩' },
  { href: '/observability', label: 'Observability',  icon: '📊' },
  { href: '/settings',      label: 'Settings',       icon: '⚙️' },
];

export interface SidebarProps {
  collapsed?: boolean;
  onToggle?: (collapsed: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed: controlledCollapsed, onToggle }) => {
  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const collapsed = controlledCollapsed ?? internalCollapsed;
  const pathname = usePathname();

  const handleToggle = () => {
    const next = !collapsed;
    setInternalCollapsed(next);
    onToggle?.(next);
  };

  return (
    <nav
      className={[styles.sidebar, collapsed ? styles['sidebar--collapsed'] : ''].join(' ')}
      aria-label="Main navigation"
    >
      <div className={styles.logo}>
        <span className={styles.logoIcon} aria-hidden="true">⚡</span>
        {!collapsed && <span className={styles.logoText}>Forge-OH</span>}
      </div>

      <ul className={styles.navList} role="list">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={[styles.navItem, active ? styles['navItem--active'] : ''].join(' ')}
                aria-current={active ? 'page' : undefined}
                title={collapsed ? item.label : undefined}
              >
                <span className={styles.navIcon} aria-hidden="true">{item.icon}</span>
                {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
              </Link>
            </li>
          );
        })}
      </ul>

      <button
        className={styles.toggle}
        onClick={handleToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? '›' : '‹'}
      </button>
    </nav>
  );
};
