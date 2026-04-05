from __future__ import annotations

import requests


class OpenListError(RuntimeError):
    pass


class OpenListClient:
    def __init__(self, config, logger, session: requests.Session | None = None):
        self.base_url = config.base_url.rstrip("/")
        self.username = config.username
        self.password = config.password
        self.timeout_seconds = config.timeout_seconds
        self.logger = logger
        self.session = session or requests.Session()
        self.token: str | None = None

    def login(self) -> str:
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password, "otp_code": ""},
            timeout=self.timeout_seconds,
        )
        payload = self._parse_response(response)
        token = payload.get("data", {}).get("token")
        if not token:
            raise OpenListError("OpenList 登录成功但没有拿到 token")
        self.token = token
        return token

    def list_metas(self) -> list[dict]:
        payload = self.request("GET", "/api/admin/meta/list")
        return payload.get("data", {}).get("content", [])

    def get_meta(self, meta_id: int) -> dict:
        payload = self.request("GET", f"/api/admin/meta/get?id={meta_id}")
        return payload["data"]

    def find_meta_by_path(self, meta_path: str) -> dict | None:
        metas = self.list_metas()
        for item in metas:
            if item.get("path") == meta_path:
                return item
        return None

    def create_meta(self, meta_payload: dict) -> None:
        self.request("POST", "/api/admin/meta/create", json_data=meta_payload)

    def update_meta(self, meta_payload: dict) -> None:
        self.request("POST", "/api/admin/meta/update", json_data=meta_payload)

    def delete_meta(self, meta_id: int) -> None:
        self.request("POST", f"/api/admin/meta/delete?id={meta_id}")

    def request(self, method: str, api_path: str, json_data: dict | None = None) -> dict:
        if not self.token:
            self.login()
        headers = {"Authorization": self.token or ""}
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{api_path}",
            json=json_data,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> dict:
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise OpenListError(f"OpenList 返回了非 JSON 内容：{response.text[:200]}") from exc

        if response.status_code >= 400:
            raise OpenListError(payload.get("message") or response.reason)
        if payload.get("code") != 200:
            raise OpenListError(payload.get("message") or "OpenList 接口返回失败")
        return payload
