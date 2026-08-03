// ESLint flat config for Next 16 + TypeScript.
// eslint-config-next@16 ships its own flat configs at
// `eslint-config-next/flat/core-web-vitals` and `eslint-config-next/flat/typescript`.
// Use these directly instead of FlatCompat (which breaks on next 16's
// circular plugin refs).
import nextCoreWebVitals from 'eslint-config-next/flat/core-web-vitals';
import nextTypeScript from 'eslint-config-next/flat/typescript';

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
      'src/tests/**',
      '**/*.test.ts',
      '**/*.test.tsx',
    ],
  },
];
