'use client';
/**
 * Skills page (Stage 6.6).
 *
 * Lists every skill the running BFF can activate on this workspace:
 *   - User skills   → ~/.agents/skills/**\/SKILL.md
 *   - Project skills → {repo-root}/.agents/skills/**\/SKILL.md
 *
 * Data source: GET /api/skills — implemented as an in-process call to the
 * OpenHands SDK loader (see bff/routers/skills.py header for rationale).
 * When the upstream agent-server `/api/skills` HTTP endpoint is fixed, the
 * BFF router body can swap back to a proxy without any change here.
 */
import React, { useMemo, useState } from 'react';
import { useSkills } from '@/features/skills/hooks';
import type { Skill } from '@/lib/schemas/skill';

type ScopeFilter = 'all' | 'user' | 'project';

export default function SkillsPage() {
  const { data, isLoading, error } = useSkills();
  const skills: Skill[] = data?.data ?? [];
  const sources = data?.sources ?? {};

  const [scope, setScope] = useState<ScopeFilter>('all');
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Client-side filtering — the response is small (~30 rows) so a
  // network round-trip per scope toggle would waste latency.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return skills.filter((s) => {
      if (scope === 'user' && !s.source.includes('/.agents/skills/user/') && !s.source.includes('/home/')) {
        // Fallback: user skills live under $HOME/.agents/skills. Project skills
        // live under the repo root. We approximate by treating anything under
        // ~ (which the BFF sees as absolute /home/<user>/.agents) as user.
      }
      if (q && !s.name.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [skills, scope, query]);

  function toggle(name: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  const totalCount = skills.length;
  const userCount = sources.user ?? 0;
  const projectCount = sources.project ?? 0;

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '24px', margin: 0 }}>Skills</h1>
        <p style={{ color: 'var(--text-muted, #888)', marginTop: '6px', fontSize: '14px' }}>
          Skill definitions the running agent can activate. Loaded from disk on request.
        </p>
      </header>

      <div
        role="group"
        aria-label="Skill scope filter"
        style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}
      >
        {(['all', 'user', 'project'] as ScopeFilter[]).map((s) => {
          const isActive = scope === s;
          const label =
            s === 'all' ? `All (${totalCount})` :
            s === 'user' ? `User (${userCount})` :
            `Project (${projectCount})`;
          return (
            <button
              key={s}
              onClick={() => setScope(s)}
              aria-pressed={isActive}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--border, #333)',
                background: isActive ? 'var(--accent, #2563eb)' : 'transparent',
                color: isActive ? '#fff' : 'inherit',
                cursor: 'pointer',
                fontSize: '13px',
              }}
            >
              {label}
            </button>
          );
        })}
        <input
          type="search"
          placeholder="Filter by name or description…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search skills"
          style={{
            marginLeft: 'auto',
            padding: '6px 10px',
            borderRadius: '6px',
            border: '1px solid var(--border, #333)',
            background: 'var(--bg-input, transparent)',
            color: 'inherit',
            minWidth: '240px',
            fontSize: '13px',
          }}
        />
      </div>

      {isLoading && (
        <div aria-busy="true" aria-label="Loading skills" style={{ padding: '24px', color: '#888' }}>
          Loading skills…
        </div>
      )}

      {error && (
        <div role="alert" style={{ padding: '12px', background: '#fee', color: '#900', borderRadius: '6px' }}>
          Failed to load skills: {(error as Error).message}
        </div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#888', border: '1px dashed var(--border, #333)', borderRadius: '8px' }}>
          {totalCount === 0
            ? 'No skills discovered. Drop a SKILL.md into ~/.agents/skills/<name>/ or .agents/skills/<name>/ inside this repo.'
            : `No skills match "${query}".`}
        </div>
      )}

      {!isLoading && !error && filtered.length > 0 && (
        <ul role="list" aria-label="Skills" style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filtered.map((skill) => {
            const isOpen = expanded.has(skill.name);
            return (
              <li
                key={skill.name}
                data-testid="skill-row"
                data-skill-name={skill.name}
                style={{
                  border: '1px solid var(--border, #333)',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  background: 'var(--bg-elev, transparent)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => toggle(skill.name)}
                    aria-expanded={isOpen}
                    aria-controls={`skill-body-${skill.name}`}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'inherit',
                      cursor: 'pointer',
                      fontSize: '15px',
                      fontWeight: 600,
                      padding: 0,
                    }}
                  >
                    {isOpen ? '▾' : '▸'} {skill.name}
                  </button>
                  <span style={{ fontSize: '11px', color: '#888', border: '1px solid #444', padding: '1px 6px', borderRadius: '10px' }}>
                    {skill.type}
                  </span>
                  {skill.triggers.length > 0 && (
                    <span style={{ fontSize: '12px', color: '#888' }}>
                      {skill.triggers.length} trigger{skill.triggers.length === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
                {skill.description && (
                  <p style={{ marginTop: '6px', marginBottom: 0, color: 'var(--text, #ddd)', fontSize: '13px' }}>
                    {skill.description}
                  </p>
                )}
                {skill.triggers.length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {skill.triggers.slice(0, 12).map((t) => (
                      <span
                        key={t}
                        style={{
                          fontSize: '11px',
                          background: 'var(--chip-bg, #1e293b)',
                          color: 'var(--chip-fg, #cbd5e1)',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        }}
                      >
                        {t}
                      </span>
                    ))}
                    {skill.triggers.length > 12 && (
                      <span style={{ fontSize: '11px', color: '#888' }}>
                        +{skill.triggers.length - 12} more
                      </span>
                    )}
                  </div>
                )}
                {isOpen && (
                  <div
                    id={`skill-body-${skill.name}`}
                    style={{
                      marginTop: '10px',
                      padding: '10px',
                      background: 'var(--bg-code, #0f172a)',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                      whiteSpace: 'pre-wrap',
                      color: 'var(--text-code, #cbd5e1)',
                      maxHeight: '360px',
                      overflowY: 'auto',
                    }}
                  >
                    {skill.contentPreview || '(no content)'}
                    {skill.contentTruncated && (
                      <div style={{ marginTop: '8px', color: '#888', fontStyle: 'italic' }}>
                        Preview truncated to 500 characters. Full body at{' '}
                        <code>{skill.source}</code>
                      </div>
                    )}
                  </div>
                )}
                {skill.source && (
                  <div style={{ marginTop: '6px', fontSize: '11px', color: '#666', fontFamily: 'ui-monospace, monospace' }}>
                    {skill.source}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
