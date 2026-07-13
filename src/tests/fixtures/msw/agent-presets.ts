const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const agentPresetsFixture = {
  total: 3,
  presets: [
    {
      id: 'preset-devstral-agentic',
      name: 'Devstral Agentic',
      description: 'Full agentic mode with Devstral Small 24B. Best for multi-file refactoring and debugging loops.',
      modelName: 'devstral-small:24b',
      backend: 'ollama',
      tools: ['edit_file', 'run_command', 'browser', 'search'],
      loopGuardEnabled: true,
      contextLoaderEnabled: true,
      updatedAt: ago(3 * 24 * 60 * 60 * 1000),
    },
    {
      id: 'preset-qwen3-fast',
      name: 'Qwen3 Fast',
      description: 'Fast scripting and quick tasks with Qwen3 14B. Lower VRAM footprint.',
      modelName: 'qwen3:14b',
      backend: 'ollama',
      tools: ['edit_file', 'run_command'],
      loopGuardEnabled: true,
      contextLoaderEnabled: false,
      updatedAt: ago(3 * 24 * 60 * 60 * 1000),
    },
    {
      id: 'preset-teaching-mode',
      name: 'Teaching Mode (Rigpa)',
      description: 'Explains every decision step-by-step. Designed for learners in Rigpa-LMS.',
      modelName: 'devstral-small:24b',
      backend: 'ollama',
      tools: ['edit_file', 'run_command'],
      loopGuardEnabled: true,
      contextLoaderEnabled: true,
      updatedAt: ago(1 * 24 * 60 * 60 * 1000),
    },
  ],
};
