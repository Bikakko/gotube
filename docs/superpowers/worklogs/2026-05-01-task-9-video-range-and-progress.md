# 任务 9：视频可拖动播放与下载阶段进度修复

## 背景

- 下载页下载某些视频时，进度条会先跑满一次，再重新跑满一次。
- 下载页弹窗和 `/watch` 播放页里，视频控件存在但拖动进度条无效。

## 根因

### 1. 下载进度重复跑满

- 当前 yt-dlp 格式优先选择 `bestvideo + bestaudio`。
- 进度回调直接把当前下载工件的百分比写到任务总进度。
- 分离音视频时，第一段工件完成会先到 100%，第二段又从 0% 开始，表现成“满两次”。

### 2. 播放页无法拖动

- 当前环境里的 `starlette.responses.FileResponse` 不支持 Range 请求。
- 浏览器视频控件需要字节范围响应才能稳定拖动。
- 前端控件本身不是主因，根因在后端流式响应能力不足。

## 修复

### 下载进度

- 给 `DownloadTask` 增加阶段元数据：
  - `download_phase_count`
  - `download_phase_index`
  - `download_phase_artifacts`
- `_extract_info()` 根据 `requested_formats` 预先标记阶段数。
- `_make_progress_hook()` 改为按阶段加权计算总进度，而不是每个工件都独占 0-100。
- 工件 key 规范化时去掉 `.part/.temp/.ytdl` 后缀，避免临时文件名与最终文件名被误判成两段。

### 视频播放

- 新增 `server/http_media.py`
- 统一提供 `build_video_stream_response(...)`
  - 普通请求返回可声明 `Accept-Ranges` 的文件响应
  - Range 请求返回 `206 Partial Content`
  - 非法 Range 返回 `416`
- `/watch` 和匿名游客流 `/api/guest-downloads/stream/...` 全部切到这个 helper。

## 验证

- 新增 `tests/test_http_media_unittest.py`
- 扩展 `tests/test_downloader_transfer_boundaries_unittest.py`
- 更新 `tests/test_main_security_unittest.py` 的静态资源路径断言
