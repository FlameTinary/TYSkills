---
type: moc
status: active
created: "{{date:YYYY-MM-DD}}"
modified: "{{date:YYYY-MM-DD}}"
tags: [moc]
---

# 🎯 Projects 总览

## 进行中
```dataview
TABLE WITHOUT ID file.link AS "项目", due AS "截止", area AS "所属领域", created AS "创建"
FROM "01-Projects"
WHERE type = "project" AND status = "active"
SORT due ASC
```

## 搁置（on-hold）
```dataview
LIST FROM "01-Projects" WHERE type = "project" AND status = "on-hold"
```

## 已完成待归档（status = done）
```dataview
TABLE WITHOUT ID file.link AS "项目", due AS "截止"
FROM "01-Projects"
WHERE type = "project" AND status = "done"
```
> 处理方式：补归档字段 → 移到 `04-Archives/01-已完成项目/` → status 改 archived

## 本周到期
```dataview
TABLE WITHOUT ID file.link AS "项目", due AS "截止"
FROM "01-Projects"
WHERE type = "project" AND status = "active" AND due <= date(today) + dur(7 days)
SORT due ASC
```
