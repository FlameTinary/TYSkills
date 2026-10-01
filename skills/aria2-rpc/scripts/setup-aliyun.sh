#!/bin/bash
# 配置阿里云盘存储（AliyundriveOpen 驱动）
# 用法: setup-aliyun.sh "<refresh_token>" [挂载路径]

set -e

ALIST_URL="http://localhost:5244"
USERNAME="admin"
MOUNT_PATH="${2:-/aliyun}"

if [ -z "$1" ]; then
    echo "用法: $0 \"<refresh_token>\" [挂载路径]"
    echo "示例: $0 \"eyJ0eXAi...\" /aliyun"
    echo ""
    echo "获取 refresh_token:"
    echo "  https://alist.nn.ci/tool/aliyundrive/request.html"
    exit 1
fi

REFRESH_TOKEN="$1"

# 从密码文件读取密码，或提示输入
PASSWORD_FILE="$HOME/.alist/admin_password.txt"
if [ -f "$PASSWORD_FILE" ]; then
    PASSWORD=$(grep -o 'password: [^ ]*' "$PASSWORD_FILE" | tail -1 | awk '{print $2}')
else
    read -s -p "请输入 AList 管理员密码: " PASSWORD
    echo ""
fi

echo "=== 配置阿里云盘（AliyundriveOpen）==="
echo "挂载路径: $MOUNT_PATH"

# 登录
LOGIN_RESULT=$(curl -s -X POST "$ALIST_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "登录失败: $LOGIN_RESULT"
    exit 1
fi
echo "登录成功"

# 检查是否已存在同名存储
EXISTING=$(curl -s -X GET "$ALIST_URL/api/admin/storage/list?page=1&per_page=100" \
  -H "Authorization: $TOKEN")

STORAGE_ID=$(echo "$EXISTING" | python3 -c "
import sys,json
d = json.load(sys.stdin)
mount = '$MOUNT_PATH'
for s in d['data']['content']:
    if s['mount_path'] == mount:
        print(s['id'])
        break
" 2>/dev/null)

# 构造 addition 配置
ADDITION=$(python3 -c "
import json
addition = {
    'refresh_token': '$REFRESH_TOKEN',
    'root_folder_id': 'root',
    'order_by': 'name',
    'order_direction': 'asc',
    'rapid_upload': False,
    'internal_upload': False
}
print(json.dumps(addition))
")

if [ -n "$STORAGE_ID" ]; then
    echo "存储已存在（ID: ${STORAGE_ID}），正在更新..."
    RESULT=$(curl -s -X POST "$ALIST_URL/api/admin/storage/update" \
      -H "Content-Type: application/json" \
      -H "Authorization: $TOKEN" \
      -d "{
        \"id\": $STORAGE_ID,
        \"mount_path\": \"$MOUNT_PATH\",
        \"order\": 1,
        \"driver\": \"AliyundriveOpen\",
        \"addition\": $(python3 -c "import json; print(json.dumps('$ADDITION'))"),
        \"remark\": \"阿里云盘\"
      }")
else
    echo "正在添加新存储..."
    RESULT=$(curl -s -X POST "$ALIST_URL/api/admin/storage/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: $TOKEN" \
      -d "{
        \"mount_path\": \"$MOUNT_PATH\",
        \"order\": 1,
        \"driver\": \"AliyundriveOpen\",
        \"addition\": $(python3 -c "import json; print(json.dumps('$ADDITION'))"),
        \"remark\": \"阿里云盘\"
      }")
fi

CODE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('code', 0))")

if [ "$CODE" == "200" ]; then
    echo "配置成功！"
else
    echo "配置结果: $RESULT"
fi

# 等待并检查状态
sleep 3
STATUS=$(curl -s -X GET "$ALIST_URL/api/admin/storage/list?page=1&per_page=100" \
  -H "Authorization: $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
mount = '$MOUNT_PATH'
for s in d['data']['content']:
    if s['mount_path'] == mount:
        print(s['status'])
        break
")

echo "存储状态: $STATUS"
if [ "$STATUS" == "work" ]; then
    echo "阿里云盘已成功挂载到 $MOUNT_PATH"
fi
