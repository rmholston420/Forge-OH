import type { Preview } from '@storybook/react';
import '../src/styles/globals.css';

const preview: Preview = {
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    backgrounds: {
      default: 'dark',
      values: [{ name: 'dark', value: '#0F1115' }, { name: 'surface', value: '#171D29' }],
    },
  },
};

export default preview;
