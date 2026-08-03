// ESLint flat config for Next 16 + TypeScript.
// eslint-config-next@16 ships flat configs at the paths below.
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';

export default [
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    ignores: [
      '.next/**',
      'node_modules/**',
      'dist/**',
      'out/**',
      'bff/**',
      'scripts/**',
      'workspace/**',
      'src/tests/**',
      '**/*.test.ts',
      '**/*.test.tsx',
    ],
  },
];
