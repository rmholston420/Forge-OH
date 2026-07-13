"""Tests for bff/routers/workspaces.py."""
import pytest
from fastapi.testclient import TestClient
from bff.tests.utils import create_test_client
from bff.routers.workspaces import _WORKSPACES

# Use the full multi-router test app so /api/auth/demo-login is available
# for issuing real tokens (correct user_id strings in _TOKENS).
client = create_test_client()

CREATE_PAYLOAD = {'name': 'My WS', 'type': 'local'}


def _auth_headers() -> dict:
    """Login as developer (write role) and return Authorization header."""
    body = client.post(
        '/api/auth/demo-login',
        json={'username': 'admin', 'password': 'password'},
    ).json()
    return {'Authorization': f"Bearer {body['token']}"}


def _delete_headers() -> dict:
    """Login as admin (delete role) and return Authorization header."""
    body = client.post(
        '/api/auth/demo-login',
        json={'username': 'admin', 'password': 'password'},
    ).json()
    return {'Authorization': f"Bearer {body['token']}"}


# ---------------------------------------------------------------------------
# GET /api/workspaces
# ---------------------------------------------------------------------------

class TestListWorkspaces:
    def test_returns_200(self):
        assert client.get('/api/workspaces').status_code == 200

    def test_returns_list(self):
        assert isinstance(client.get('/api/workspaces').json(), list)

    def test_seed_workspaces_present(self):
        assert len(client.get('/api/workspaces').json()) >= 2

    def test_items_have_id_and_type(self):
        for ws in client.get('/api/workspaces').json():
            assert 'id' in ws and 'type' in ws


# ---------------------------------------------------------------------------
# GET /api/workspaces/{id}
# ---------------------------------------------------------------------------

class TestGetWorkspace:
    def test_known_id_returns_200(self):
        assert client.get('/api/workspaces/ws-1').status_code == 200

    def test_unknown_id_returns_404(self):
        assert client.get('/api/workspaces/ghost').status_code == 404

    def test_correct_workspace_returned(self):
        body = client.get('/api/workspaces/ws-1').json()
        assert body['id'] == 'ws-1'

    def test_disk_fields_present(self):
        body = client.get('/api/workspaces/ws-1').json()
        assert 'diskUsageMb' in body and 'diskLimitMb' in body


# ---------------------------------------------------------------------------
# POST /api/workspaces  — requires write role
# ---------------------------------------------------------------------------

class TestCreateWorkspace:
    def test_unauthenticated_returns_401(self):
        assert client.post('/api/workspaces', json=CREATE_PAYLOAD).status_code == 401

    def test_returns_200_with_auth(self):
        assert client.post('/api/workspaces', json=CREATE_PAYLOAD,
                           headers=_auth_headers()).status_code == 200

    def test_initial_status_is_provisioning(self):
        body = client.post('/api/workspaces', json=CREATE_PAYLOAD,
                           headers=_auth_headers()).json()
        assert body['status'] == 'provisioning'

    def test_initial_run_count_zero(self):
        body = client.post('/api/workspaces', json=CREATE_PAYLOAD,
                           headers=_auth_headers()).json()
        assert body['runCount'] == 0

    def test_name_echoed(self):
        body = client.post('/api/workspaces', json={'name': 'Echo', 'type': 'docker'},
                           headers=_auth_headers()).json()
        assert body['name'] == 'Echo'

    def test_invalid_type_returns_422(self):
        r = client.post('/api/workspaces', json={'name': 'Bad', 'type': 'kubernetes'},
                        headers=_auth_headers())
        assert r.status_code == 422

    def test_missing_name_returns_422(self):
        assert client.post('/api/workspaces', json={'type': 'local'},
                           headers=_auth_headers()).status_code == 422

    def test_persisted_in_store(self):
        body = client.post('/api/workspaces', json=CREATE_PAYLOAD,
                           headers=_auth_headers()).json()
        assert body['id'] in _WORKSPACES

    def test_env_vars_accepted(self):
        payload = {**CREATE_PAYLOAD, 'envVars': [{'key': 'TOKEN', 'value': 'abc', 'masked': True}]}
        body = client.post('/api/workspaces', json=payload,
                           headers=_auth_headers()).json()
        assert len(body['envVars']) == 1


# ---------------------------------------------------------------------------
# PATCH /api/workspaces/{id}  — requires write role
# ---------------------------------------------------------------------------

class TestUpdateWorkspace:
    def _ws_id(self) -> str:
        return client.post('/api/workspaces', json=CREATE_PAYLOAD,
                           headers=_auth_headers()).json()['id']

    def test_unauthenticated_returns_401(self):
        assert client.patch('/api/workspaces/ws-1',
                            json={'name': 'x'}).status_code == 401

    def test_updates_name(self):
        wid = self._ws_id()
        body = client.patch(f'/api/workspaces/{wid}',
                            json={'name': 'Renamed'},
                            headers=_auth_headers()).json()
        assert body['name'] == 'Renamed'

    def test_unknown_id_returns_404(self):
        r = client.patch('/api/workspaces/ghost',
                         json={'name': 'x'},
                         headers=_auth_headers())
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{id}  — requires delete role (admin only)
# ---------------------------------------------------------------------------

class TestDeleteWorkspace:
    def test_unauthenticated_returns_401(self):
        assert client.delete('/api/workspaces/ws-1').status_code == 401

    def test_deletes_known_workspace(self):
        wid = client.post('/api/workspaces', json=CREATE_PAYLOAD,
                          headers=_auth_headers()).json()['id']
        # Admin has delete role
        assert client.delete(f'/api/workspaces/{wid}',
                             headers=_delete_headers()).status_code == 200
        assert client.get(f'/api/workspaces/{wid}').status_code == 404

    def test_unknown_id_returns_404(self):
        assert client.delete('/api/workspaces/ghost',
                             headers=_delete_headers()).status_code == 404


# ---------------------------------------------------------------------------
# POST /api/workspaces/{id}/reset  — requires write role
# ---------------------------------------------------------------------------

class TestResetWorkspace:
    def test_unauthenticated_returns_401(self):
        assert client.post('/api/workspaces/ws-1/reset').status_code == 401

    def test_known_id_returns_200(self):
        assert client.post('/api/workspaces/ws-1/reset',
                           headers=_auth_headers()).status_code == 200

    def test_unknown_id_returns_404(self):
        assert client.post('/api/workspaces/ghost/reset',
                           headers=_auth_headers()).status_code == 404

    def test_reset_clears_disk_usage(self):
        body = client.post('/api/workspaces/ws-1/reset',
                           headers=_auth_headers()).json()
        assert body['diskUsageMb'] == 0

    def test_reset_status_is_idle(self):
        body = client.post('/api/workspaces/ws-1/reset',
                           headers=_auth_headers()).json()
        assert body['status'] == 'idle'
