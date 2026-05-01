## 任务

4.7.x 第一轮安全与性能热修。

## 已完成

1. 安全止血
   - `admin_api.py` 收口内部异常泄露，统一只返回业务级错误信息。
   - 批量删除接口增加单次请求上限（100 项）。
   - `config.py` 增加 `GOTUBE_HIDDEN_PATH` 白名单校验。
   - `http_media.py` 修复 `Content-Disposition` 文件名转义问题。
   - `downloader.py` 增加缩略图 URL 的私网/本地地址过滤，降低 SSRF 风险。

2. 认证与下载热路径
   - `auth.py` 将过期 token 清理从“每次鉴权全表加载”改为节流后的批量 `UPDATE`。
   - `auth.py` 将 token 验证改为 `AuthToken + User` 单次联查。
   - `downloader.py` 将缩略图下载和 ffprobe 完整性校验迁移到线程池，避免阻塞事件循环。

3. 后台性能热点
   - `video_library.py` 将后台媒体列表的 owner/source 查询改为批量查询，消除双 N+1。
   - `downloader.py` 为 hash 索引增加 TTL 缓存与锁，移除命中失败后的再次全盘扫描。
   - `db.py` 初始化 SQLite 时启用 `WAL` 和 `synchronous=NORMAL`。
   - `health_checks.py` 将运行日志读取改为流式尾部读取，避免整文件载入内存。
   - `invites.py` 将邀请码消费改为原子 `UPDATE`，减少并发竞争窗口。

4. 回归测试
   - 新增：
     - `tests/test_config_security_unittest.py`
     - `tests/test_downloader_security_unittest.py`
   - 扩展：
     - `tests/test_admin_management_unittest.py`
     - `tests/test_http_media_unittest.py`
   - 本轮通过测试：
     - `tests.test_admin_management_unittest`
     - `tests.test_downloader_security_unittest`
     - `tests.test_health_checks_unittest`
     - `tests.test_http_media_unittest`
     - `tests.test_config_security_unittest`
     - `tests.test_auth_roles_unittest`
     - `tests.test_invites_unittest`

## 暂未处理

1. `api.py` / `video_library.py` 的分页缺失。
2. `admin_api.py` `_list_all_videos()` 的全量磁盘扫描与 Python 内存筛选。
3. `admin_api.py` ZIP 导出内存占用问题。
4. `main.py` CORS 白名单配置化。
5. 指纹算法统一与 CRC32 升级。
6. `_tasks` 长期运行的容量治理。
7. “上帝文件”拆分（结构治理，未纳入本轮热修）。

## 备注

- 本轮控制在 4.7.x 范围内，优先做能显著降低风险和热点开销的修复。
- 终端操作全程使用 UTF-8 显式读取，避免脚本与中文文本再次发生编码污染。
