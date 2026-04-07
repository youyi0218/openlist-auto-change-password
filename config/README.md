# config 配置说明

仓库内只保留 `config/config.example.json` 模板。

首次使用请先复制：

```bash
cp config/config.example.json config/config.json
```

Windows PowerShell：

```powershell
Copy-Item config\config.example.json config\config.json
```

然后再修改 `config/config.json`。`config/config.json` 已加入 `.gitignore`，不会再被提交到 GitHub。

## openlist
- `baseUrl`：OpenList 地址，例如 `http://127.0.0.1:5244`
- `username`：管理员用户名
- `password`：管理员密码
- `timeoutSeconds`：请求超时秒数

## passwordPolicy
- `length`：密码长度
- `useLowercase` / `useUppercase` / `useNumbers` / `useSymbols`：是否启用对应字符类型
- `symbols`：启用符号时允许使用的符号集合

## targets
- `path`：要设置元信息密码的 OpenList 路径
- `createWhenMissing`：元信息不存在时是否自动创建
- `createDefaults`：自动创建元信息时的默认参数

## schedule
- `enabled`：是否启用定时轮换
- `cron`：Cron 表达式
- `timezone`：时区
- `runOnStart`：容器启动后是否立即先执行一次

## html
- `title`：页面标题
- `passwordHint`：密码提示文案
- `templateFile`：HTML 模板路径
- `outputFile`：生成后的 HTML 文件路径
- `buttons`：底部跳转按钮列表

## cloudflare
- `enabled`：是否启用 Cloudflare Pages 发布
- `projectName`：Pages 项目名
- `accountId`：Cloudflare Account ID
- `apiToken`：Cloudflare API Token
- 如果暂时不需要发布到 Cloudflare，请保持 `enabled=false`
