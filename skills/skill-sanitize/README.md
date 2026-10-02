# skill-sanitize

> 本技能是 [TYSkills](../../README.md) 技能集合的一部分：把本目录复制或软链到你的 agent 技能目录即可使用，
> 不需要安装器或账号。仓库级的技能列表与目录结构见主 README。

## 简介

把一个技能里**属于某台机器、属于作者本人**的内容清干净，让它「换一台机器、换一个人，照样能用」。
四件事：

1. **审计**：`scripts/audit_skill.py` 扫全目录，按 high/medium/low 分级报出本机痕迹 ——
   家目录路径、用户名、主机名、外接盘卷标、局域网 IP、私有域名、个人服务名、真实邮箱，
   以及令牌/密码/私钥/refresh_token/Cookie/含密码的 URL、写死的代理端口，
   并顺带检查脱敏改写有没有把文件改坏（frontmatter 起止、BOM/CRLF）。
   默认还会拿**本机**的用户名与主机名当判据。
2. **按类处置**：每条命中给出四种处置之一 —— 删除（秘密）、参数化（本机特有的值）、占位（示例值）、
   保留并写理由（公共知识，如 AList 默认端口 5244）。处置记录留在报告里。
3. **私有值落配置文件**：要私有化的东西（路径、端口、密钥、站点命令、代理）迁到
   `~/.<技能名>/<技能名>.conf`，只提交 `*.conf.template`；配 `assets/conf_loader.py` 读取，
   优先级 命令行参数 > 环境变量 > 配置文件 > 内置默认；没有配置文件时给出「缺什么、去哪配」的报错。
4. **留痕**：文档里必须保留的反面示例用 `audit-skip: 理由` 就地记账；报告归档在本地。

技能边界：**只做脱敏**。跨平台适配、给其他 agent 打包安装、发布到仓库都不归它管。

## 依赖

- `python3`（3.8+，仅标准库），也可以脱离 agent 单独当命令行工具用

## 使用方法

```bash
# 审计一个技能目录（退出码 0 = 没有达到 --fail-level 的问题）
python3 scripts/audit_skill.py /path/to/skill

# 更严 + 输出 JSON 便于聚合 + 顺手写一份处置报告
python3 scripts/audit_skill.py /path/to/skill --fail-level medium --json --report 脱敏报告.md

# 补上只有你知道的专属词（用户名、主机名、域名、站点名、盘标），一行一词
python3 scripts/audit_skill.py /path/to/skill --terms ~/.config/skill-sanitize/local-terms.txt
```

- 报告内含命中原文，**只留本地或私有仓库**。
- `assets/private.conf.template` 是给被脱敏技能用的配置模板；
  `assets/conf_loader.py` 是可直接抄走的配置加载器。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/leak-taxonomy.md` | 泄漏分类库：每类长什么样、为什么算泄漏、怎么改（含 before/after） |
| `references/report-template.md` | 脱敏报告模板（交付给用户看的处置清单） |

## 免责声明

本技能只提供工具与流程，不包含、不内置、不推荐任何内容站点或第三方服务凭据。
技能中的示例路径、主机名、服务名、令牌一律为占位符，不含作者机器的真实信息。

## License

MIT
