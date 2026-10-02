---
type: moc
status: active
created: "{{date:YYYY-MM-DD}}"
modified: "{{date:YYYY-MM-DD}}"
tags: [moc]
---

# 🗂️ Areas 总览

```dataview
TABLE WITHOUT ID file.link AS "领域", review-cycle AS "回顾周期", modified AS "最近更新", status AS "状态"
FROM "02-Areas"
WHERE type = "area"
SORT file.name ASC
```

## 需要本月回顾的领域
```dataview
LIST FROM "02-Areas"
WHERE type = "area" AND review-cycle = "monthly"
SORT modified ASC
```
