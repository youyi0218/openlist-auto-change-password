# OpenList 自动修改元信息密码（Python）

这是一个用于自动修改 OpenList 元信息密码的 Python 工具，支持：
- 仅修改现有元信息的 `password` 字段
- 元信息不存在时自动创建
- 按计划任务自动轮换密码
- 生成密码展示 HTML 页面
- 可选发布到 Cloudflare Pages
- 通过 GitHub Actions 自动构建并发布 GHCR Docker 镜像

## 仓库清理说明
- `参考.txt`、`README.me`、`docs/`、`outputs/`、`config/config.test.json` 都不再保留在仓库里
- 仓库不再跟踪 `config/config.json`
- 公开仓库仅保留 `config/config.example.json` 作为模板

## 本地使用

### 1. 复制配置模板
```bash
cp config/config.example.json config/config.json
```

Windows PowerShell：
```powershell
Copy-Item config\config.example.json config\config.json
```

### 2. 修改你的本地配置
重点修改：
- `openlist.baseUrl`
- `openlist.username`
- `openlist.password`
- `targets`
- `html.buttons`
- 如需发布到 Cloudflare，再填写 `cloudflare.projectName / accountId / apiToken`

### 3. 本地运行
```bash
python -m pip install -r requirements.txt
python main.py validate-config --config config/config.json
python main.py run-once --config config/config.json
python main.py daemon --config config/config.json
```

## Docker / GHCR 使用
主分支推送后，GitHub Actions 会自动构建并发布镜像到：

```text
ghcr.io/youyi0218/openlist-auto-change-password:latest
```

推荐直接使用仓库里的 `docker-compose.yml`：

```bash
docker compose pull
docker compose up -d
```

它会把本地的 `./config`、`./dist`、`./output`、`./logs` 挂载到容器内，所以你只要本地改 `config/config.json`，拉取新的 GHCR 镜像后仍然可以直接使用。
