import React from 'react';
import styles from './Tabs.module.css';

export type TabsVariant = 'underline' | 'pill' | 'segmented';

export interface Tab {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  variant?: TabsVariant;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, activeTab, onTabChange, variant = 'underline', className = '' }) => {
  const classes = [styles.tabs, styles[`tabs--${variant}`], className].join(' ');

  return (
    <div className={classes} role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-disabled={tab.disabled}
          tabIndex={activeTab === tab.id ? 0 : -1}
          className={[
            styles.tab,
            activeTab === tab.id ? styles['tab--active'] : '',
            tab.disabled ? styles['tab--disabled'] : '',
          ].join(' ')}
          onClick={() => !tab.disabled && onTabChange(tab.id)}
          disabled={tab.disabled}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};
