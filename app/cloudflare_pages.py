from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


API_BASE = "https://api.cloudflare.com/client/v4"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UPLOAD_FILES = 1000


class CloudflarePagesError(RuntimeError):
    pass


class CloudflareNotFound(CloudflarePagesError):
    pass


@dataclass(slots=True)
class AssetFile:
    relative_path: str
    absolute_path: Path
    sha256: str
    size: int
    content_type: str


def _decode_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise CloudflarePagesError(f"Cloudflare 返回了非 JSON 内容：{response.text[:300]}") from exc


def _extract_error_message(payload: dict[str, Any]) -> str:
    errors = payload.get("errors") or []
    if errors:
        return "; ".join(str(item.get("message") or item) for item in errors)
    return str(payload.get("result") or payload.get("message") or "未知错误")


def md5_hex(binary: bytes) -> str:
    import hashlib

    return hashlib.md5(binary).hexdigest()


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        body = token.split(".")[1]
        padded = body + "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except Exception:
        return {}


class CloudflarePagesClient:
    def __init__(self, config, logger, session: requests.Session | None = None):
        self.config = config
        self.logger = logger
        self.session = session or requests.Session()

    def verify_api_token(self) -> dict[str, Any]:
        return self._api_request("GET", "/user/tokens/verify")

    def resolve_account_id(self) -> str:
        if self.config.account_id:
            return self.config.account_id
        result = self._api_request("GET", "/accounts?page=1&per_page=50")
        if len(result) == 1:
            return result[0]["id"]
        raise CloudflarePagesError("Cloudflare 账号不止一个，请在 config 中填写 cloudflare.accountId")

    def ensure_project(self, account_id: str) -> None:
        try:
            self._api_request(
                "GET",
                f"/accounts/{account_id}/pages/projects/{self.config.project_name}",
            )
            return
        except CloudflareNotFound:
            if not self.config.create_project_if_missing:
                raise
        self.logger.info("Cloudflare Pages 项目不存在，正在自动创建：%s", self.config.project_name)
        self._api_request(
            "POST",
            f"/accounts/{account_id}/pages/projects",
            json_body={
                "name": self.config.project_name,
                "production_branch": self.config.branch,
            },
        )

    def deploy_directory(self, directory: Path) -> dict[str, Any]:
        if not self.config.enabled:
            return {"deployed": False, "reason": "cloudflare disabled"}
        if not self.config.api_token.strip():
            raise CloudflarePagesError("cloudflare.enabled=true 时必须填写 cloudflare.apiToken")

        account_id = self.resolve_account_id()
        self.ensure_project(account_id)
        files = self.collect_files(directory)
        upload_jwt = self._get_upload_jwt(account_id)
        max_files_allowed = _decode_jwt_payload(upload_jwt).get("max_file_count_allowed")
        if isinstance(max_files_allowed, int) and len(files) > max_files_allowed:
            raise CloudflarePagesError(f"当前套餐最多允许 {max_files_allowed} 个文件，本次有 {len(files)} 个文件")

        missing_hashes = self._check_missing_hashes(upload_jwt, files)
        self._upload_missing_files(upload_jwt, files, missing_hashes)
        self._upsert_hashes(upload_jwt, files)
        manifest = {f"/{item.relative_path}": item.sha256 for item in files}
        deployment = self._create_deployment(account_id, manifest, directory.name)
        deployment_detail = self._wait_for_deployment(account_id, deployment["id"])
        aliases = deployment_detail.get("aliases") or []
        alias = next((item for item in aliases if str(item).endswith(".pages.dev")), "")
        return {
            "deployed": True,
            "accountId": account_id,
            "deploymentId": deployment["id"],
            "projectName": self.config.project_name,
            "url": deployment.get("url") or deployment_detail.get("url"),
            "alias": alias,
        }

    def collect_files(self, directory: Path) -> list[AssetFile]:
        files: list[AssetFile] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(directory).as_posix()
            binary = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            files.append(
                AssetFile(
                    relative_path=relative_path,
                    absolute_path=path,
                    sha256=md5_hex(binary),
                    size=len(binary),
                    content_type=content_type,
                )
            )
        if not files:
            raise CloudflarePagesError("没有可部署的静态文件，请先生成 HTML 页面")
        return files

    def _api_request(self, method: str, api_path: str, json_body: dict[str, Any] | None = None) -> Any:
        response = self.session.request(
            method=method,
            url=f"{API_BASE}{api_path}",
            headers={**_bearer_headers(self.config.api_token), "Content-Type": "application/json"},
            json=json_body,
            timeout=30,
        )
        payload = _decode_json_response(response)
        if response.status_code == 404:
            raise CloudflareNotFound(_extract_error_message(payload))
        if response.status_code >= 400 or payload.get("success") is False:
            raise CloudflarePagesError(_extract_error_message(payload))
        return payload.get("result")

    def _upload_request(self, method: str, api_path: str, upload_jwt: str, json_body: Any) -> Any:
        response = self.session.request(
            method=method,
            url=f"{API_BASE}{api_path}",
            headers={**_bearer_headers(upload_jwt), "Content-Type": "application/json"},
            json=json_body,
            timeout=60,
        )
        payload = _decode_json_response(response)
        if response.status_code >= 400 or payload.get("success") is False:
            raise CloudflarePagesError(_extract_error_message(payload))
        return payload.get("result")

    def _get_upload_jwt(self, account_id: str) -> str:
        result = self._api_request(
            "GET",
            f"/accounts/{account_id}/pages/projects/{self.config.project_name}/upload-token",
        )
        jwt = result.get("jwt")
        if not jwt:
            raise CloudflarePagesError("未获取到 Cloudflare Pages upload JWT")
        return jwt

    def _check_missing_hashes(self, upload_jwt: str, files: list[AssetFile]) -> list[str]:
        if self.config.skip_caching:
            return [item.sha256 for item in files]
        return self._upload_request(
            "POST",
            "/pages/assets/check-missing",
            upload_jwt,
            {"hashes": [item.sha256 for item in files]},
        )

    def _upload_missing_files(self, upload_jwt: str, files: list[AssetFile], missing_hashes: list[str]) -> None:
        hash_set = set(missing_hashes)
        if not hash_set:
            self.logger.info("Cloudflare 端已缓存全部文件，本次无需重新上传静态文件。")
            return

        pending = [item for item in files if item.sha256 in hash_set]
        chunk: list[dict[str, Any]] = []
        chunk_bytes = 0
        chunk_count = 0
        for item in pending:
            binary = item.absolute_path.read_bytes()
            payload = {
                "key": item.sha256,
                "value": base64.b64encode(binary).decode("utf-8"),
                "metadata": {"contentType": item.content_type},
                "base64": True,
            }
            approx_size = len(payload["value"])
            if chunk and (chunk_bytes + approx_size > MAX_UPLOAD_BYTES or chunk_count >= MAX_UPLOAD_FILES):
                self._upload_request("POST", "/pages/assets/upload", upload_jwt, chunk)
                chunk = []
                chunk_bytes = 0
                chunk_count = 0
            chunk.append(payload)
            chunk_bytes += approx_size
            chunk_count += 1
        if chunk:
            self._upload_request("POST", "/pages/assets/upload", upload_jwt, chunk)
        self.logger.info("Cloudflare 静态资源上传完成，本次上传 %s 个文件。", len(pending))

    def _upsert_hashes(self, upload_jwt: str, files: list[AssetFile]) -> None:
        self._upload_request(
            "POST",
            "/pages/assets/upsert-hashes",
            upload_jwt,
            {"hashes": [item.sha256 for item in files]},
        )

    def _create_deployment(self, account_id: str, manifest: dict[str, str], output_dir_name: str) -> dict[str, Any]:
        response = self.session.post(
            f"{API_BASE}/accounts/{account_id}/pages/projects/{self.config.project_name}/deployments",
            headers=_bearer_headers(self.config.api_token),
            data={"branch": self.config.branch},
            files={
                "manifest": (None, json.dumps(manifest, ensure_ascii=False), "application/json"),
            },
            timeout=60,
        )
        payload = _decode_json_response(response)
        if response.status_code >= 400 or payload.get("success") is False:
            raise CloudflarePagesError(_extract_error_message(payload))
        return payload.get("result")

    def _wait_for_deployment(self, account_id: str, deployment_id: str) -> dict[str, Any]:
        import time

        last_detail: dict[str, Any] | None = None
        for _ in range(self.config.poll_attempts):
            detail = self._api_request(
                "GET",
                f"/accounts/{account_id}/pages/projects/{self.config.project_name}/deployments/{deployment_id}",
            )
            last_detail = detail
            latest_stage = detail.get("latest_stage") or {}
            if latest_stage.get("name") == "deploy" and latest_stage.get("status") == "success":
                return detail
            if latest_stage.get("name") == "deploy" and latest_stage.get("status") == "failure":
                try:
                    logs = self._api_request(
                        "GET",
                        f"/accounts/{account_id}/pages/projects/{self.config.project_name}/deployments/{deployment_id}/history/logs?size=1000000",
                    )
                    if logs.get("data"):
                        last_line = logs["data"][-1].get("line", "")
                    else:
                        last_line = "部署失败，但没有返回详细日志。"
                except Exception:  # noqa: BLE001
                    last_line = "部署失败，且拉取日志失败。"
                raise CloudflarePagesError(last_line)
            time.sleep(self.config.poll_interval_seconds)
        if last_detail is None:
            raise CloudflarePagesError("Cloudflare 部署状态轮询失败")
        return last_detail
