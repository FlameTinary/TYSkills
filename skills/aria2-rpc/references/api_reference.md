# Aria2 JSON-RPC API 参考

## 目录
- [认证机制](#认证机制)
- [任务管理方法](#任务管理方法)
- [状态查询方法](#状态查询方法)
- [全局状态方法](#全局状态方法)
- [BT 相关方法](#bt-相关方法)
- [任务状态字段说明](#任务状态字段说明)
- [常见选项参数](#常见选项参数)
- [错误码](#错误码)

---

## 认证机制

所有方法的第一个参数必须是认证令牌：
```
"params": ["token:你的rpc-secret", ...其他参数]
```

如果 aria2 配置了 `--rpc-secret=xxx`，则必须在每个请求的 params 数组第一位添加 `token:xxx`。

---

## 任务管理方法

### aria2.addUri
添加 HTTP/FTP/磁力链接下载任务。

**参数**：
1. `secret` — 认证令牌
2. `uris` — string[]，下载链接数组
3. `options` — object（可选），任务选项
4. `position` — integer（可选），插入任务队列的位置

**返回**：string，任务 GID

**示例**：
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "aria2.addUri",
  "params": [
    "token:secret",
    ["magnet:?xt=urn:btih:abc123"],
    {"dir": "/path/to/Downloads", "seed-time": "0"}
  ]
}
```

### aria2.addTorrent
添加 BT 种子文件任务。

**参数**：
1. `secret`
2. `torrent` — string，base64 编码的 .torrent 文件内容
3. `uris` — string[]（可选），web-seed 链接
4. `options` — object（可选）

**返回**：string，任务 GID

### aria2.addMetalink
添加 Metalink 格式任务（较少使用）。

---

## 状态查询方法

### aria2.tellStatus
获取单个任务详细状态。

**参数**：
1. `secret`
2. `gid` — string，任务 GID
3. `keys` — string[]（可选），只返回指定字段

**返回**：任务对象（见下方字段说明）

### aria2.tellActive
获取所有活动中的下载任务。

**参数**：
1. `secret`
2. `keys` — string[]（可选）

**返回**：任务对象数组

### aria2.tellWaiting
获取等待中的任务（含暂停的任务）。

**参数**：
1. `secret`
2. `offset` — integer，从第几个开始
3. `num` — integer，返回数量
4. `keys` — string[]（可选）

**返回**：任务对象数组

### aria2.tellStopped
获取已停止/已完成的任务。

**参数**：
1. `secret`
2. `offset` — integer
3. `num` — integer
4. `keys` — string[]（可选）

**返回**：任务对象数组

---

## 任务控制方法

### aria2.pause
暂停任务。

**参数**：`[secret, gid]`
**返回**：string，GID

### aria2.unpause
恢复暂停的任务。

**参数**：`[secret, gid]`
**返回**：string，GID

### aria2.forcePause
强制暂停（不等待当前操作完成）。

### aria2.remove
移除任务（停止下载并从队列删除，保留已下载文件）。

**参数**：`[secret, gid]`

### aria2.forceRemove
强制移除。

### aria2.removeDownloadResult
从已完成/已停止列表中删除任务记录。

**参数**：`[secret, gid]`

### aria2.pauseAll / aria2.unpauseAll
批量暂停/恢复所有任务。

---

## 全局状态方法

### aria2.getGlobalStat
获取全局统计信息。

**参数**：`[secret]`

**返回字段**：
- `downloadSpeed` — 全局下载速度（字节/秒）
- `uploadSpeed` — 全局上传速度
- `numActive` — 活动任务数
- `numWaiting` — 等待任务数
- `numStopped` — 已停止任务数

### aria2.getVersion
获取 aria2 版本和功能列表。

**参数**：`[secret]`

### aria2.shutdown / aria2.forceShutdown
关闭 aria2 进程。

---

## BT 相关方法

### aria2.getPeers
获取 BT 任务的 peer 列表。

**参数**：`[secret, gid]`

### aria2.getServers
获取 HTTP/FTP 任务的服务器信息。

**参数**：`[secret, gid]`

### aria2.tellOption
获取任务的选项设置。

**参数**：`[secret, gid]`

### aria2.changeOption
修改运行中任务的选项（如下载速度限制）。

**参数**：`[secret, gid, options]`

---

## 任务状态字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `gid` | string | 任务唯一ID |
| `status` | string | 状态：active/waiting/paused/error/complete/removed |
| `totalLength` | string | 总大小（字节） |
| `completedLength` | string | 已完成大小 |
| `uploadLength` | string | 已上传大小 |
| `bitfield` | string | 位域（哪些块已下载） |
| `downloadSpeed` | string | 下载速度（字节/秒） |
| `uploadSpeed` | string | 上传速度 |
| `connections` | string | 连接数 |
| `numSeeders` | string | 做种者数量 |
| `seeder` | string | 是否正在做种 |
| `files` | array | 文件列表 |
| `bittorrent` | object | BT 元信息（名称、大小等） |

**status 状态枚举**：
- `active` — 正在下载
- `waiting` — 排队等待中
- `paused` — 已暂停
- `error` — 出错
- `complete` — 已完成
- `removed` — 已删除

---

## 常见选项参数

添加任务时可传入的 options 对象：

```json
{
  "dir": "/path/to/save",
  "out": "自定义文件名",
  "max-connection-per-server": "16",
  "min-split-size": "10M",
  "split": "16",
  "max-tries": "5",
  "timeout": "60",
  "seed-time": "0",
  "seed-ratio": "1.0",
  "bt-max-peers": "100",
  "bt-tracker": "udp://...",
  "header": ["User-Agent: xxx", "Cookie: xxx"]
}
```

---

## 错误码

RPC 错误时返回 `error` 对象：
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "error": {
    "code": 1,
    "message": "Unknown method"
  }
}
```

| 错误码 | 含义 |
|--------|------|
| 1 | 未知方法 |
| 2 | 无效参数 |
| 3 | 内部错误 |
| 4 | 资源不可用 |
| 5 | 暂停失败 |
| 6 | 暂停失败（已暂停） |
| 7 | 继续失败 |
| 8 | 继续失败（未暂停） |
| 9 | 移除失败 |
| 10 | 移除失败（未在队列中） |
| 11 | 所选文件不存在 |
| 12 | 下载已完成 |
| 13 | 未找到任务（GID 不存在） |
| 14 | 未找到下载结果 |
| 15 | 元信息未就绪（磁力还在获取 metadata） |

---

## 参考链接

- 官方文档：https://aria2.github.io/manual/en/html/aria2c.html#rpc-methods
