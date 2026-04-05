from __future__ import annotations

import json
from pathlib import Path

from app.cloudflare_pages import CloudflarePagesClient
from app.config import CloudflareConfig


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append((method, url, headers, json))
        if url.endswith('/user/tokens/verify'):
            return FakeResponse(200, {"success": True, "result": {"status": "active"}, "errors": []})
        if url.endswith('/accounts?page=1&per_page=50'):
            return FakeResponse(200, {"success": True, "result": [{"id": "acc-1"}], "errors": []})
        if url.endswith('/pages/projects/pan_password'):
            return FakeResponse(404, {"success": False, "errors": [{"message": "not found"}], "result": None})
        if url.endswith('/pages/projects') and method == 'POST':
            return FakeResponse(200, {"success": True, "result": {"name": "pan_password"}, "errors": []})
        if url.endswith('/upload-token'):
            return FakeResponse(200, {"success": True, "result": {"jwt": 'aaa.eyJtYXhfZmlsZV9jb3VudF9hbGxvd2VkIjoxMDB9.bbb'}, "errors": []})
        if url.endswith('/pages/assets/check-missing'):
            return FakeResponse(200, {"success": True, "result": [json['hashes'][0]], "errors": []})
        if url.endswith('/pages/assets/upload'):
            return FakeResponse(200, {"success": True, "result": {"ok": True}, "errors": []})
        if url.endswith('/pages/assets/upsert-hashes'):
            return FakeResponse(200, {"success": True, "result": {"ok": True}, "errors": []})
        if url.endswith('/deployments/deploy-1'):
            return FakeResponse(200, {"success": True, "result": {"latest_stage": {"name": "deploy", "status": "success"}, "aliases": ['https://pan_password.pages.dev'], "url": 'https://deploy.example.com'}, "errors": []})
        raise AssertionError(f'Unexpected request: {method} {url}')

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        self.calls.append(('POST', url, headers, data, files))
        if url.endswith('/deployments'):
            return FakeResponse(200, {"success": True, "result": {"id": 'deploy-1', "url": 'https://deploy.example.com'}, "errors": []})
        raise AssertionError(f'Unexpected POST: {url}')


def test_cloudflare_deploy_flow(tmp_path: Path):
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html>hello</html>', encoding='utf-8')
    config = CloudflareConfig(
        enabled=True,
        project_name='pan_password',
        account_id='',
        api_token='token',
        branch='main',
        create_project_if_missing=True,
        skip_caching=False,
        poll_attempts=2,
        poll_interval_seconds=1,
    )
    logger = type('Logger', (), {'info': lambda *args, **kwargs: None})()
    client = CloudflarePagesClient(config, logger, session=FakeSession())
    result = client.deploy_directory(dist)
    assert result['deployed'] is True
    assert result['projectName'] == 'pan_password'
    assert result['accountId'] == 'acc-1'
    assert result['alias'] == 'https://pan_password.pages.dev'
