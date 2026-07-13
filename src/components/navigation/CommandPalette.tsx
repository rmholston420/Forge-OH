import React, { useEffect, useRef, useState } from 'react';
import styles from './CommandPalette.module.css';

export interface CommandItem {
  id: string;
  label: string;
  description?: string;
  action: () => void;
  shortcut?: string;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  commands?: CommandItem[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onClose, commands = [] }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setTimeout(() => inputRef.current?.focus(), 50);
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  if (!open) return null;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Command palette" onClick={onClose}>
      <div className={styles.palette} onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className={styles.input}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a command…"
          aria-label="Command search"
        />
        <ul className={styles.list} role="listbox">
          {filtered.length === 0 && (
            <li className={styles.empty}>No commands found</li>
          )}
          {filtered.map((cmd) => (
            <li key={cmd.id} className={styles.item} role="option" onClick={() => { cmd.action(); onClose(); }}>
              <span className={styles.label}>{cmd.label}</span>
              {cmd.description && <span className={styles.desc}>{cmd.description}</span>}
              {cmd.shortcut && <span className={styles.shortcut}>{cmd.shortcut}</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
