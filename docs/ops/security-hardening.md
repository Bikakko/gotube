# GoTube 4.2.0 安全与发布硬化说明

本文记录 4.2.0 这轮已经落地的应用层安全收口，以及服务器侧建议继续补齐的规则。

## 已落地的应用层硬化

### 1. 探测路径不再返回 200

应用现在会对常见扫描目标直接返回 `404`，包括但不限于：

- `/.git/*`
- `/.env`
- `/.svn/*`
- `/wp-*`
- `/composer.json`
- `/backup*`
- `/config.*`

这一步的目标不是“隐藏一切”，而是避免把无意义探测喂成一个成功页面，降低继续被扫的概率。

### 2. 未知路径不再兜底成页面

过去未知路径会落到前端页面并返回 `200`。现在不存在的路径会返回真正的 `404`。

这能避免：

- 扫描器把站点识别成“有可利用页面”；
- 误把异常请求写成正常访问；
- 日志和监控失真。

### 3. 默认响应头

应用层已经追加：

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: same-origin`
- 基础 `Content-Security-Policy`

当前 CSP 允许站内内联脚本和样式，因为现有页面仍存在内联代码。后续如果前端进一步收口，可再继续收紧。

### 4. 访问日志增加时间标签

`wk.sh` 启动 Gunicorn 时会显式设置带时间字段的 access log 格式，并开启 `--capture-output`，便于把应用输出统一写入日志文件。

## 服务器侧建议继续补齐

应用层已经挡住明显的误判入口，但真正的防扫和限流仍应放在 Nginx 或同类反向代理上。

### 1. 建议的 Nginx 拒绝规则

```nginx
location ~* ^/(\.git|\.env|\.svn|\.hg) {
    return 404;
}

location ~* ^/(wp-|wordpress|composer\.(json|lock)|backup|backups|dump|dumps|config) {
    return 404;
}
```

### 2. 建议的基础响应头

如果你使用 Nginx，建议也在代理层保留相同语义的响应头，避免后续换服务入口时丢失：

```nginx
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
```

### 3. 建议的限流

至少对明显高频探测路径加限流。重点不是“防住一切”，而是降低日志污染和资源浪费。

### 4. Fail2ban

如果服务器长期暴露公网，建议对 Nginx 访问日志接入 Fail2ban，优先封禁：

- 短时间内大量请求不存在路径；
- 集中扫描 `/.git`、`/.env`、`wp-login.php` 等路径；
- 重复命中 Basic Auth 或管理认证失败。

## 运维检查建议

上线 4.2.0 后，至少手动确认：

1. `/.git/config` 返回 `404`
2. 一个随机路径返回 `404`
3. `/health` 正常
4. `server.log` 中访问日志带时间
5. `wk.sh init` 会生成并使用 `www_dist`
