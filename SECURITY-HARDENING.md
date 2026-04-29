# GoTube 安全加固

本文记录当前已经落地的应用层安全收口，以及服务器侧仍建议补齐的代理层规则。

## 已落地的应用层收口

### 1. 常见探测路径不再返回 200

应用会直接对以下类型路径返回 `404`：

- `/.git/*`
- `/.env`
- `/.svn/*`
- `/wp-*`
- `/composer.json`
- `/backup*`
- `/config.*`

### 2. 未知路径返回真实 404

不存在的路由不再兜底落到前端页面，也不会再返回伪 `200`。

### 3. 基础响应头

应用层已补充：

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: same-origin`
- 基础 `Content-Security-Policy`

### 4. 访问日志带时间字段

`wk.sh` 启动 Gunicorn 时会显式设置 access log 格式，并统一写入日志文件。

## 代理层建议

如果线上暴露公网上，建议继续在 Caddy 或 Nginx 层补齐拦截和限流。

### Nginx 示例

```nginx
location ~* ^/(\.git|\.env|\.svn|\.hg) {
    return 404;
}

location ~* ^/(wp-|wordpress|composer\.(json|lock)|backup|backups|dump|dumps|config) {
    return 404;
}
```

### 建议保留的响应头

```nginx
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
```

### 限流与封禁

建议至少覆盖：

- 高频扫描不存在路径
- 集中探测 `/.git`、`/.env`、`/wp-login.php`
- 管理认证失败的重复尝试

如果服务长期暴露公网，建议接入 Fail2ban。

## 上线后检查

至少手工确认：

1. `/.git/config` 返回 `404`
2. 随机不存在路径返回 `404`
3. `/health` 正常
4. `server.log` 中访问日志带时间
5. `wk.sh init` 能构建并使用 `www_dist`
