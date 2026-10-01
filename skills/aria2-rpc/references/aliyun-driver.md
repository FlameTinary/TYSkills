# 阿里云盘驱动配置（AliyundriveOpen）

## 驱动选择

使用 **AliyundriveOpen**（阿里云盘开放平台），这是当前推荐的官方驱动。

旧版 `Aliyundrive` 驱动已逐步弃用，可能遇到 token 刷新失败。

## 获取 refresh_token

### 方法一：AList 官方工具（推荐）

1. 打开 https://alist.nn.ci/tool/aliyundrive/request.html
2. 点击「扫描登录」
3. 用阿里云盘手机 App 扫码
4. 在手机上确认授权
5. 页面跳转后显示 refresh_token，完整复制

### 方法二：手动从网页获取

1. 登录 https://www.aliyundrive.com
2. 打开浏览器开发者工具（F12）
3. Application → Local Storage → token
4. 复制 refresh_token 字段

## 添加存储

### 通过脚本

```bash
bash scripts/setup-aliyun.sh "<refresh_token>"
```

### 通过 Web UI

1. 登录 AList
2. 左下角「管理」
3. 左侧「存储」→「添加」
4. 填写配置：

| 字段 | 值 |
|------|-----|
| 驱动 | AliyundriveOpen |
| 挂载路径 | `/aliyun` |
| 根文件夹ID | `root` |
| 刷新令牌 | refresh_token |
| 排序方式 | name |
| 排序方向 | asc |

5. 点击「保存」

## 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| root_folder_id | 根目录文件夹ID，`root` 表示全部文件 | root |
| refresh_token | 刷新令牌，用于自动续期 | 必填 |
| order_by | 文件排序字段：name / size / updated_at | name |
| order_direction | 排序方向：asc / desc | asc |
| rapid_upload | 是否启用秒传 | false |
| internal_upload | 是否使用内部上传接口 | false |

## 验证挂载

存储状态显示为 **work** 即成功。

通过 API 验证：

```bash
# 列出根目录
curl -X POST http://localhost:5244/api/fs/list \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{"path":"/aliyun","page":1,"per_page":10}'
```

## 常见问题

### failed to refresh token

原因：
- refresh_token 已过期或失效
- 使用了错误的驱动（旧版 Aliyundrive）
- token 复制不完整

解决：
1. 重新扫码获取新的 refresh_token
2. 确认驱动选择 AliyundriveOpen
3. 重新保存存储配置

### token 有效期

refresh_token 通常有效期较长，AList 会自动刷新并更新存储配置。如果长期不用可能失效，重新获取即可。

### 挂载特定文件夹

将 `root_folder_id` 改为目标文件夹的 ID：

1. 在 AList 中进入目标文件夹
2. 浏览器地址栏或 API 响应中可获取文件夹 ID
3. 填入 root_folder_id 字段
