// ESLint flat config for Next 16 + TypeScript.
// eslint-config-next@16 ships flat configs at the paths below.
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    // Register the react-hooks plugin so our rule overrides below resolve.
    // (eslint-config-next re-exports the rules but flat config requires the
    // plugin object to be registered in the same config that references its
    // rule names.)
    plugins: { 'react-hooks': reactHooks },
  },
  {
    // Rule tuning. We keep genuine bug-catching rules as errors but
    // downgrade style/strictness rules that don't correlate with defects
    // in a small local-first codebase.
    rules: {
      // Style / strictness — downgrade to warning.
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/no-unused-expressions': 'warn',

      // React 19 / eslint-plugin-react-hooks v7 introduced new rules that
      // fire on many legitimate patterns (writing refs from render, setState
      // in effects for reconciliation). Downgrade to warnings so real bugs
      // (still surfaced) don't block CI on our defensive patterns.
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/exhaustive-deps': 'warn',

      // We intentionally use <img> for run artifact screenshots (dynamic
      // URLs to the BFF, no next/image optimization possible).
      '@next/next/no-img-element': 'warn',
    },
  },
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
      // Python virtual environments — never lint vendored JS shipped inside
      // pip packages (litellm swagger, lmnr SDK, etc).
      '.oh-venv/**',
      '.venv/**',
      'venv/**',
      '**/*.min.js',
      '**/*.min.cjs',
      '**/*.bundle.js',
      'playwright-report/**',
      'playwright-artifacts/**',
      'test-results/**',
      'coverage/**',
      '.cov-html-bff/**',
      'storybook-static/**',
    ],
  },
];
