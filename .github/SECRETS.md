# Required GitHub Actions Secrets

Configure these in **Settings → Secrets and variables → Actions**.

| Secret | Required | Description |
|--------|----------|-------------|
| `NEXTAUTH_SECRET` | Yes | Random 32+ char string for NextAuth JWT signing. Generate: `openssl rand -base64 32` |
| `CODECOV_TOKEN` | No | Codecov upload token for coverage reporting |
| `GITHUB_CLIENT_ID` | No | GitHub OAuth App client ID (for GitHub provider in NextAuth) |
| `GITHUB_CLIENT_SECRET` | No | GitHub OAuth App client secret |
| `RIGPA_PLUGIN_URL` | No | Base URL of your Rigpa-LMS instance (e.g. `https://your-lms.example.com`) |

> `GITHUB_TOKEN` is automatically provided by Actions — no configuration needed.

## Generating NEXTAUTH_SECRET

```bash
openssl rand -base64 32
```

Or use: https://generate-secret.vercel.app/32

## Environment Variables (not secrets)

Set these as **repository variables** (Settings → Secrets and variables → Variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_BFF_URL` | `http://localhost:8000` | BFF base URL for frontend API calls |
| `PLAYWRIGHT_BASE_URL` | `http://localhost:3000` | Base URL for Playwright E2E tests |
