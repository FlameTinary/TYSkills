# AList API 参考

基础地址：`http://localhost:5244`

## 认证

### 登录

```
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

响应：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJ...",
    "device_key": "..."
  }
}
```

后续请求在 Header 中携带：
```
Authorization: <token>
```

## 文件操作

### 列出目录

```
POST /api/fs/list
```

请求体：
```json
{
  "path": "/aliyun/文件夹",
  "password": "",
  "page": 1,
  "per_page": 100,
  "refresh": false
}
```

响应字段：
- `name`：文件名
- `is_dir`：是否目录
- `size`：大小（字节）
- `modified`：修改时间
- `sign`：签名

### 获取文件信息与直链

```
POST /api/fs/get
```

请求体：
```json
{
  "path": "/aliyun/文件夹/文件.mp4",
  "password": ""
}
```

响应：
```json
{
  "code": 200,
  "data": {
    "name": "文件.mp4",
    "size": 1234567890,
    "is_dir": false,
    "raw_url": "https://dl1-v6.aliyundrive.cloud/...",
    "modified": "2026-01-01T00:00:00Z"
  }
}
```

`raw_url` 即文件直链，可直接交给 aria2 下载。

### 搜索文件

```
POST /api/fs/search
```

请求体：
```json
{
  "parent": "/aliyun",
  "keywords": "关键词",
  "page": 1,
  "per_page": 50
}
```

## 存储管理

### 获取存储列表

```
GET /api/admin/storage/list?page=1&per_page=100
```

### 添加存储

```
POST /api/admin/storage/create
```

请求体：
```json
{
  "mount_path": "/aliyun",
  "order": 1,
  "driver": "AliyundriveOpen",
  "addition": "{\"refresh_token\":\"...\",\"root_folder_id\":\"root\"}",
  "remark": "阿里云盘"
}
```

`addition` 是 JSON 字符串，不是嵌套对象。

### 更新存储

```
POST /api/admin/storage/update
```

请求体需包含 `id` 字段，其余同创建。

### 删除存储

```
POST /api/admin/storage/delete
```

请求体：
```json
{
  "id": 1
}
```

## 下载任务

### 获取离线下载任务列表

```
GET /api/admin/task/offline_download/undone
```

## 配合 aria2/a2 使用

### 流程

1. 登录获取 token
2. 调用 `/api/fs/get` 获取 `raw_url`
3. 用 a2 添加下载：

```bash
a2 add "<raw_url>"
```

### 示例脚本

见 `scripts/a2-alist`，封装了完整流程：

```bash
a2-alist "/aliyun/电影/电影.mkv" /输出目录
```

## 状态码

| code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 请求错误（如密码错误） |
| 401 | 未认证 |
| 403 | 无权限 |
| 500 | 服务器错误 |

## 注意事项

- 直链通常有有效期（约 15 分钟），获取后尽快开始下载
- 下载开始后即使直链过期也不影响已建立的连接
- `addition` 字段必须是 JSON 字符串（双重序列化）
- 管理类 API 需要管理员权限的 token
