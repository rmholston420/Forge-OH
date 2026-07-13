# Changelog

## 2026-07-13

### Fixed

- Restored BFF auth routing by mounting `auth.router` in `bff/main.py` with `prefix="/api"`.
- Exposed working auth endpoints in the live backend, including:
  - `POST /api/auth/login`
  - `POST /api/auth/demo-login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Updated frontend credentials auth flow in `src/lib/auth/config.ts` to authenticate against `${NEXT_PUBLIC_BFF_URL}/api/auth/login`.
- Added FastAPI `CORSMiddleware` in `bff/main.py` for:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- Resolved browser CORS failure where `OPTIONS /api/runs` returned `405 Method Not Allowed`, which had caused the Runs page to fail with `Failed to fetch`.

### Verified

- `POST /api/auth/login` returns `200 OK` with a payload containing `token`, `user.email`, and `user.role`.
- NextAuth credentials callback now returns `200` instead of `401 CredentialsSignin`.
- Login succeeds with:
  - `admin@forge.dev`
  - `password123`
- Browser redirects successfully to `/runs`.
- Runs page loads real data from `http://127.0.0.1:8081/api/runs` in the working local setup.

### Notes

- The current local setup allows the browser to call the BFF directly, which requires CORS to be configured correctly.
- The long-term architecture should still prefer same-origin Next.js route handlers or proxy endpoints to avoid browser CORS coupling and keep transport normalization centralized.
