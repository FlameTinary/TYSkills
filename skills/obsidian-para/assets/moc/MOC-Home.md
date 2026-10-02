---
type: moc
status: active
created: "{{date:YYYY-MM-DD}}"
modified: "{{date:YYYY-MM-DD}}"
tags: [moc, para]
---

# 🏠 知识库首页

## 🎯 正在进行的项目
```dataview
TABLE WITHOUT ID file.link AS "项目", due AS "截止", area AS "领域"
FROM "01-Projects"
WHERE type = "project" AND status = "active"
SORT due ASC
```

## 🗂️ 我的领域
```dataview
TABLE WITHOUT ID file.link AS "领域", review-cycle AS "回顾周期", modified AS "最近更新"
FROM "02-Areas"
WHERE type = "area" AND status = "active"
SORT file.name ASC
```

## 📥 收件箱（未处理）
```dataview
LIST FROM "99-Inbox" SORT file.mtime DESC
```

## 🔗 直达
- [[MOC-Projects总览]]
- [[MOC-Areas总览]]
- [[MOC-Resources总览]]
