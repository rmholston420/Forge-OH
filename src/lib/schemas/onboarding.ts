import { z } from 'zod';

export const OnboardingStepSchema = z.object({
  id:             z.string(),
  title:          z.string(),
  description:    z.string(),
  targetSelector: z.string(), // CSS selector for spotlight cutout
  completed:      z.boolean().default(false),
  skippable:      z.boolean().default(true),
});

export type OnboardingStep = z.infer<typeof OnboardingStepSchema>;

export const DEFAULT_TOUR_STEPS: OnboardingStep[] = [
  {
    id: 'sidebar',
    title: 'Navigate with the sidebar',
    description: 'Access Runs, Workspaces, Tools & MCP, Secrets, and Settings from the left rail.',
    targetSelector: '[data-tour="sidebar"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'new-run',
    title: 'Start your first run',
    description: 'Click “New Run” to launch an agent task. Choose a workspace, agent preset, and describe the task.',
    targetSelector: '[data-tour="new-run-btn"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'run-detail-tabs',
    title: 'Explore run details',
    description: 'Each run has tabs: Overview, Files (Monaco diff), Terminal (xterm), Browser, Metrics, Trace, and Artifacts.',
    targetSelector: '[data-tour="run-detail-tabs"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'plan-rail',
    title: 'Track the agent’s plan',
    description: 'The Plan Rail shows each step the agent intends to take, with live status updates as it executes.',
    targetSelector: '[data-tour="plan-rail"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'approval-banner',
    title: 'Approve or reject steps',
    description: 'When the agent needs your input, a full-width banner appears. Review and approve or reject before it continues.',
    targetSelector: '[data-tour="approval-banner"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'workspaces',
    title: 'Manage workspaces',
    description: 'Workspaces are isolated environments (local, Docker, or remote) where agents run. Create and manage them here.',
    targetSelector: '[data-tour="workspaces-page"]',
    completed: false,
    skippable: true,
  },
  {
    id: 'settings',
    title: 'Customize Forge-OH',
    description: 'Set your preferred model, agent defaults, theme, accent color, and keyboard shortcuts in Settings.',
    targetSelector: '[data-tour="settings-link"]',
    completed: false,
    skippable: true,
  },
];
