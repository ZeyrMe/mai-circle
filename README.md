# 群关系 · `zeyr.mai-circle`

> 人工锚定的熟人谱系、同行 Bot 归属标记、非线性阻尼动态热络度，以及供全生态复用的 `@set:` 公共集合中心。

![Version](https://img.shields.io/badge/version-0.2.0-green)
![MaiBot](https://img.shields.io/badge/MaiBot-1.4.8%2B-blue)
![SDK](https://img.shields.io/badge/SDK-2.23.0-teal)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## 核心特性

- **关系标签字典 + 一人多标签**：预置并允许自定义 `普通群友 / 老熟人 / 损友 / 同行Bot` 等标签（每个标签独立拥有专属提示词、基础亲疏度、说话倍率与松口加成），单个人物可同时挂载多个标签。
- **同行 Bot 精确识别**：显式标记“谁家的什么 Bot”（`owner_name` + `bot_role`），供见闻、生活等插件跳过同行 Bot 发言、避免互刷复读，同时正常调侃搭话。
- **双层 Master 严格隔离**：
  - `admins` 仅用于程序层 `/关系`、`/待办`、`/唤醒` 等管理命令鉴权，**永远不进入大模型上下文**；
  - 对话层仅通过标签引导亲切感，死守“不承认自己是 Bot”的拟真边界。
- **非线性阻尼动态热络度（群聊/私聊分算）**：
  - 坚决拒绝线性刷分——采用**单日有效回合对数饱和**（15 句认真互动接近饱和，刷屏 300 句水话无额外收益）+ **7 天半衰期回弹至人工锚点**，兼顾近期聊得投机与长期不变质的基线；
  - 同一人在大群和一对一私聊的热络度分别核算。
- **全生态公共集合 `@set:` 复用中心**：在一个插件里维护好 `观察群`、`熟人群` 等公共集合，其余 5 个插件直接填 `@set:观察群` 或 `@tag:同行Bot` 即可同步生效。

---

## 安装与快速配置

将 `mai-circle/` 放入宿主 `plugins/` 目录并重启 MaiBot。支持独立安装；推荐在 WebUI 的卡片列表里添加标签、人物和公共集合。

`config.toml` 示例（所有账号与群号请按实际情况填写，勿提交代码库）：

```toml
enabled = true

[[group_sets]]
name = "观察群"
members = ["111222333"]

[[people]]
user_id = "987654"
name = "阿云"
tags = ["老熟人"]
persona_master = true
custom_note = "经常半夜写代码"

[[people]]
user_id = "654321"
name = "小Q"
is_bot = true
tags = ["同行Bot"]
owner_name = "阿明"
bot_role = "群管"

[[admins]]
platform = "qq"
user_id = "987654"
```

---

## 工具、命令、接口与 WebUI 控制台

### 对话工具（`@Tool`）
| 工具名 | 参数 | 作用 |
|---|---|---|
| `query_circle_relation` | `user`, `platform="qq"` | 当对话提及不在场的第三方人物时，手动查询其人工关系或 Bot 归属（当前活跃发言人已自动轻量注入，不代替宿主动态记忆画像） |

### 管理命令（需在 `admins` 名单内）
| 命令格式 | 效果 |
|---|---|
| `/关系 + <QQ号> <标签1,标签2>` | 为指定用户设置或更新人工关系标签 |
| `/关系 bot <QQ号> <主人称呼> <角色定位>` | 快捷登记同行 Bot 及其归属 |
| `/关系` 或 `/关系 列表` | 列出当前群关系里已登记的所有人物 |
| `/关系 - <QQ号>` | 删除已记录的关系条目（支持对配置预设条目软删除） |

### 对外联动接口（`@API(..., version="1")`）
- `is_bot(platform, user_id)` / `is_admin(platform, user_id)` / `filter_humans(messages)`
- `get_mentions_context(user_ids, platform, scope_kind="group")`
- `get_chat_weight(platform, user_ids, scope_kind="group")`：输出对称说话权重与 `shy` 松口加成
- `resolve_scope_ref(ref)`：解析 `@set:` 与 `@tag:` 引用

### WebUI 运行时控制台（`config_widgets`）
| 控件 | 类型 | 说明 |
|---|---|---|
| `运行状态与生效范围` | 实时状态 | 显示已登记人类熟人/同行 Bot 数量、已配置 `@set:` 集合以及近期热络联系人 |
| `刷新公共集合缓存` | 一键按钮 | 刷新作用域集合缓存 |
| `重置动态热络度` | 二次确认按钮 | 清空动态热络累积偏移，全部联系人恢复到人工标签锚点 |

---

## 生态联动与注意事项

- **与 `mai-day` 频率协调让位**：当 `mai-day` 在线并接管该会话时，`mai-circle` 自动让位给 `mai-day` 做 `时段权重 × 关系权重` 乘法合成；未装 `mai-day` 或该会话由 `mai-circle` 独立接手时，自动切换为独立调权。
- **不替代宿主记忆**：本插件只处理“谁是谁家 Bot、硬关系与公共集合”，日常聊出来的印象记忆依然由 MaiBot 原生 A-Memorix 承担。

<details>
<summary>开发、门禁与安全审计（独立仓库维护）</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

- 包含完整 Git 文本编码/换行/尾随空格检查、Ruff lint/format、`pytest`、依赖一致性检查及 `pip_audit` / `gitleaks` CI 流水线。

</details>
