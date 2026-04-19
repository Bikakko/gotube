# 任务 13 工作日志：URL 规范化与复用增强

## 背景

任务 10 验收中发现同一视频在不同平台 URL 形态下仍可能重复下载，尤其是：

- YouTube 链接可能携带播放进度、分享参数，或使用 `youtu.be` 短链。
- Bilibili 链接常带 `spm_id_from`、`vd_source` 等跟踪参数。
- X/Twitter 链接可能在 `twitter.com/{user}/status/{id}` 与 `x.com/i/status/{id}` 之间切换。

任务 13 的目标是增强复用命中率，同时不改变数据库结构，不强行把 yt-dlp 下载 URL 改成 canonical URL。

## 修复内容

- 新增 `server.url_normalizer`：
  - 定义 `NormalizedMediaUrl`，包含 `original_url`、`canonical_url`、`platform`、`media_key`。
  - YouTube：
    - 移除播放进度和分享跟踪参数。
    - `youtu.be/{id}`、`/watch?v={id}`、`/shorts/{id}`、`/embed/{id}` 统一到 `https://www.youtube.com/watch?v={id}`。
  - Bilibili：
    - 提取 `/video/{BV/av}`。
    - 删除跟踪参数，保留分 P 语义参数 `p`。
  - X/Twitter：
    - `twitter.com/{user}/status/{id}` 和 `x.com/i/status/{id}` 统一到 `https://x.com/i/status/{id}`。
  - 未知平台：
    - 删除常见跟踪和播放进度参数，保留其他查询参数并排序。
- `server.video_library.normalize_source_url()` 改为委托 `normalize_media_url().canonical_url`：
  - 现有 `MediaSource.normalized_url` 不改结构即可受益。
  - `get_asset_from_existing_source()` 和 `create_item_from_existing_source()` 自动使用新的 canonical 规则。
- 下载提交路径增强：
  - `server.api.add_task()` 在 URL 校验后计算 canonical `source_url`。
  - 游客复用查找使用 canonical URL。
  - 排队下载任务保留原始 URL 给 yt-dlp 使用，同时将 canonical URL 存为 `task.source_url`。
- 任务去重增强：
  - `QueueManager` 同客户端重复任务判断改为比较 canonical `source_url`。
  - `DownloadTask` 增加 `source_url` 与 `original_url`。
  - `meta.json` 写入 canonical `url` 和 `original_url`，便于后续审计。

## 回归测试

新增 `tests/test_url_normalizer_unittest.py`，覆盖：

- YouTube 播放进度和分享参数清理。
- YouTube 短链归一。
- Bilibili 跟踪参数清理和分 P 参数保留。
- X/Twitter 域名和路径归一。
- 未知平台常见跟踪参数清理。
- `video_library.normalize_source_url()` 使用 canonical 结果。
- 队列重复任务判断使用 canonical `source_url`。

扩展 `tests/test_video_library_unittest.py`：

- X/Twitter URL 变体能命中同一 `MediaAsset`，并为另一个用户创建视频库条目。

已运行：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_url_normalizer_unittest tests.test_video_library_unittest
.\venv\Scripts\python.exe -m unittest tests.test_url_normalizer_unittest tests.test_video_library_unittest tests.test_download_cancellation_unittest tests.test_downloader_transfer_boundaries_unittest
.\venv\Scripts\python.exe -m py_compile server\url_normalizer.py server\api.py server\downloader.py server\queue_manager.py server\video_library.py
```

结果均通过。

## 后续注意

- 本任务没有新增数据库字段。`media_key` 当前作为规范化结果存在，后续如需要更强索引能力，可再设计迁移字段。
- yt-dlp 仍使用用户提交的原始 URL 下载，降低 canonical URL 对平台解析兼容性的影响。
- 游客之间的正在下载任务仍按各自 session 隔离，本任务重点增强已有媒体和同客户端任务复用。
