# MOC 设计与 Dataview 查询库

## 目录

1. MOC 是什么
2. MOC 文件清单
3. Dataview 前置准备
4. 通用 Dataview 查询库

> 可直接复制的成品 MOC 见 `assets/moc/`（MOC-Home / Projects / Areas / Resources 总览）。

---

## 1. MOC 是什么

MOC（Map of Content）是一篇**索引笔记**，手动 + 自动地把某个主题下的所有笔记组织到一起。

- 文件夹 = 物理存放位置（一篇笔记只能在一个文件夹）
- MOC = 逻辑目录（一篇笔记可以同时出现在多个 MOC 里）

没有 MOC 的知识库就是一堆散文件；MOC 是让笔记"长在一起"的骨架。

---

## 2. MOC 文件清单

在 `MOC/` 目录建以下笔记：

| MOC 文件 | 作用 |
|---|---|
| `MOC-Home.md` | 全库首页，链接到所有 MOC |
| `MOC-Projects总览.md` | 所有项目的汇总（进行中/搁置/待归档/本周到期） |
| `MOC-Areas总览.md` | 所有领域的汇总 |
| `MOC-Resources总览.md` | 所有资源分类的汇总 |
| `MOC-健康管理.md` 等 | 每个 Area 一篇（与 `02-Areas/` 领域笔记对应） |

---

## 3. Dataview 前置准备

Obsidian 设置 → 第三方插件 → 关闭安全模式 → 浏览安装 **Dataview** 插件，并在插件设置打开「Enable JavaScript Queries」和「Enable Inline Queries」。

---

## 4. 通用 Dataview 查询库

### 4.1 自动列出所有进行中的 Project

```dataview
TABLE WITHOUT ID
  file.link AS "项目",
  due AS "截止日期",
  area AS "所属领域",
  created AS "创建日期"
FROM "01-Projects"
WHERE type = "project" AND status = "active"
SORT due ASC
```

### 4.2 自动列出所有 Active 的 Area

```dataview
TABLE WITHOUT ID
  file.link AS "领域",
  review-cycle AS "回顾周期",
  modified AS "最近更新"
FROM "02-Areas"
WHERE type = "area" AND status = "active"
SORT file.name ASC
```

### 4.3 列出最近新增的 Resource（10 条）

```dataview
TABLE WITHOUT ID
  file.link AS "资源笔记",
  source AS "来源",
  author AS "作者",
  created AS "收录日期"
FROM "03-Resources"
WHERE type = "resource"
SORT created DESC
LIMIT 10
```

### 4.4 列出本周到期的项目

```dataview
TABLE WITHOUT ID
  file.link AS "项目",
  due AS "截止日期"
FROM "01-Projects"
WHERE type = "project" AND status = "active" AND due <= date(today) + dur(7 days)
SORT due ASC
```

### 4.5 列出所有等待处理的 Inbox

```dataview
LIST
FROM "99-Inbox"
SORT file.mtime DESC
```

### 4.6 搁置的项目

```dataview
LIST
FROM "01-Projects"
WHERE type = "project" AND status = "on-hold"
```

### 4.7 已完成待归档的项目

```dataview
TABLE WITHOUT ID
  file.link AS "项目",
  due AS "截止"
FROM "01-Projects"
WHERE type = "project" AND status = "done"
```

### 4.8 三个月没动过的资源（考虑归档）

```dataview
TABLE WITHOUT ID
  file.link AS "资源",
  file.mtime AS "最后修改"
FROM "03-Resources"
WHERE file.mtime < date(today) - dur(90 days)
SORT file.mtime ASC
```

### 4.9 Area 页：本领域进行中的项目

```dataview
TABLE WITHOUT ID
  file.link AS "项目",
  due AS "截止日期",
  status AS "状态"
FROM "01-Projects"
WHERE area = this.file.link AND status = "active"
SORT due ASC
```

### 4.10 Area 页：本领域相关资源

```dataview
TABLE WITHOUT ID
  file.link AS "资源",
  source AS "来源"
FROM "03-Resources"
WHERE area = this.file.link
SORT file.mtime DESC
LIMIT 10
```
