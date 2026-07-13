import type { BrowserSessionListResponse } from '../../../lib/schemas/browser';

const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const browserFixture: BrowserSessionListResponse = {
  total: 1,
  sessions: [
    {
      sessionId: 'browser-session-001',
      runId: 'run-001',
      currentUrl: 'https://docs.python.org/3/library/dataclasses.html',
      title: 'dataclasses — Data Classes — Python 3.13 documentation',
      startTime: ago(9 * 60 * 1000),
      endTime: ago(7 * 60 * 1000),
      viewportWidth: 1280,
      viewportHeight: 800,
      steps: [
        {
          stepId: 'step-001',
          actionType: 'navigate',
          url: 'https://docs.python.org/3/library/dataclasses.html',
          timestamp: ago(9 * 60 * 1000),
          success: true,
        },
        {
          stepId: 'step-002',
          actionType: 'screenshot',
          timestamp: ago(8 * 60 * 1000 + 30 * 1000),
          success: true,
        },
        {
          stepId: 'step-003',
          actionType: 'scroll',
          value: '400',
          timestamp: ago(8 * 60 * 1000),
          success: true,
        },
      ],
    },
  ],
};
