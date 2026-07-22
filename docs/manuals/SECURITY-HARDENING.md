# GoTube 安全加固与防范指南 (v4.10.0)

本文记录 GoTube 已落地的应用层安全措施以及生产环境下反向代理（Nginx / Caddy）侧的安全建议。

---

## 一、 应用层已落地的安全防护

### 1. 弱隐藏路径 (Hidden Path) 说明
- `GOTUBE_HIDDEN_PATH`（如 `/7777`）仅作为避免被扫描器直接扫到下载页的弱保护，不作为真正的鉴权边界。
- 真实的访问控制依赖于 **HTTPS 加密**、**Bearer Token 签名** 以及管理员/用户权限校验。

### 2. 敏感路径探针拦截 (404 响应)
FastAPI 应用层已内置自动过滤与拦截机制，对以下常见探针扫描路径统一直接返回 `404 Not Found`：
- `/.git/*`, `/.env*`, `/.svn/*`
- `/wp-*`, `/wordpress/*`, `/composer.json`
- `/backup*`, `/config.*`

### 3. SSRF (服务端请求伪造) 缩略图防护
在下载第三方平台视频缩略图时，应用层内置了 `is_safe_thumbnail_url` 安全校验：
- 拒绝解析至 `127.0.0.1`、`localhost` 或任何内网/局域网私有 IP（如 `10.x.x.x`, `192.168.x.x`）的图片链接。
- 若域名无法解析或属于内网，自动拦截本地下载请求并静默降级为远程 URL 展示。

### 4. 安全响应头 (Security Headers)
应用层已自动注入基础安全响应头：
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: same-origin`
- `Content-Security-Policy`

---

## 二、 生产代理层加固建议 (Nginx 示例)

建议在生产环境反向代理层强制开启 HTTPS 并补齐防护：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # 1. 禁用敏感路径探针
    location ~* ^/(\.git|\.env|\.svn|\.hg) {
        return 404;
    }
    location ~* ^/(wp-|wordpress|composer\.(json|lock)|backup|dumps|config) {
        return 404;
    }

    # 2. 安全响应头
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy same-origin always;

    # 3. 反向代理至 GoTube
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```
