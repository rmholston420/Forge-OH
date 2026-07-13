
## Auth quickstart

The BFF exposes a simple demo auth flow for local development:

- `/api/auth/demo-login` — accepts a demo username/password and returns a bearer token.
- `/api/auth/me` — returns the current user, given a valid `Authorization` header.
- Protected routes (e.g. `/api/plugins`, `/api/secrets`, `/api/runs`) require `Authorization: Bearer <token>`.

### Demo login (admin user)

Use the built-in demo credentials:

```bash
cd ~/Forge-OH
source .venv/bin/activate

curl -i -X POST http://127.0.0.1:8081/api/auth/demo-login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"password"}'
```

On success, the response will include a JSON body with a `token` field, for example:

```jsonc
{
  "token": "YOUR_DEMO_TOKEN",
  "email": "admin@forge.dev",
  "role": "admin"
}
```

Copy that `token` value for the next steps.

### Using the token

Use the token in an `Authorization` header for protected routes:

```bash
# Replace YOUR_DEMO_TOKEN with the value from demo-login
TOKEN=YOUR_DEMO_TOKEN

curl -i http://127.0.0.1:8081/api/auth/me \
  -H "Authorization: Bearer ${TOKEN}"

curl -i http://127.0.0.1:8081/api/plugins \
  -H "Authorization: Bearer ${TOKEN}"
```

- `/api/auth/me` should return the admin demo user (e.g. `admin@forge.dev` with role `admin`).
- `/api/plugins` will return `[]` until you configure plugins, but `200 OK` confirms auth is working.

### Notes

- These demo credentials are intended for local development only.
- The token is backed by an in-memory store in `bff.auth_state` and is not persisted across process restarts.
- For tests, additional tokens and roles are seeded directly in the test suite (see `bff/tests/test_auth_router.py` and `bff/tests/test_rbac.py`).

