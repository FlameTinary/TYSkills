---
type: moc
status: active
created: "{{date:YYYY-MM-DD}}"
modified: "{{date:YYYY-MM-DD}}"
tags: [moc]
---

# 📚 Resources 总览

## 最近新增（10 条）
```dataview
TABLE WITHOUT ID file.link AS "资源", source AS "来源", author AS "作者", created AS "收录"
FROM "03-Resources"
WHERE type = "resource"
SORT created DESC
LIMIT 10
```

## 按来源标签分类
```dataview
TABLE WITHOUT ID file.link AS "资源", tags AS "标签"
FROM "03-Resources"
WHERE type = "resource" AND contains(tags, "source")
SORT file.name ASC
```

## 三个月没动过的资源（考虑归档）
```dataview
TABLE WITHOUT ID file.link AS "资源", file.mtime AS "最后修改"
FROM "03-Resources"
WHERE file.mtime < date(today) - dur(90 days)
SORT file.mtime ASC
```
