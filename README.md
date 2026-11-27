# 群关系（mai-circle）

可以自定义的人物标识和好感度系统

![Version](https://img.shields.io/badge/version-0.2.0-brightgreen)
![MaiBot](https://img.shields.io/badge/MaiBot-1.4.8%2B-2f81f7)
![SDK](https://img.shields.io/badge/SDK-2.23.0-0e8a16)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab)
![Standalone](https://img.shields.io/badge/独立运行-支持-blue)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## 功能介绍

- **自定义人物标签**：在标签字典中自由设置称呼模板、基础亲疏度、说话意愿倍率与私密话题松口加成，一人可同时挂多个标签。
- **其他 Bot 识别与防互刷**：标记群内其他机器人及其归属后，自动降低回复权重，并通知 `mai-insights` / `mai-day` 过滤这些机器人的发言。
- **稳定的动态好感度**：采用单日对数上限与半衰期回落机制，随真实互动温和波动并自动向标签基准靠拢，群聊和私聊分别统计。
- **全生态公共集合与权限**：维护 `@set:集合名` 供所有插件复用，同时保存仅在程序层生效、不写入提示词的管理员名单。

## 效果示例

- **熟人与备注生效**：标记 `老熟人` 与备注后，对话上下文会附带对应称呼与语气引导，平时回复也会略微积极。
- **其他 Bot 防互刷**：标记 `is_bot = true` 后发言倍率自动降低，群聊里不再跟其他机器人无限来回接龙。
- **跨插件名单复用**：在公共集合建好 `观察群` 后，其他插件的生效范围填写 `@set:观察群` 即可同步生效。

## 如何使用

1. 将 `mai-circle/` 放入宿主 `plugins/` 目录并重启，打开 **群关系** 配置页。
2. 在 **人物名单** 中添加熟人或群内其他 Bot 的账号、称呼和标签；若对方是机器人，勾选 **是其他 Bot** 并填写归属和定位。
3. 在 **公共集合** 中建立常用群集合（如 `观察群`），其余插件即可直接填写 `@set:观察群`。

<details>
<summary>config.toml 配置示例</summary>

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
custom_note = "经常熬夜写代码"

[[people]]
user_id = "654321"
name = "小Q"
is_bot = true
tags = ["同行Bot"]
owner_name = "阿明"
bot_role = "群管"

[affinity]
enabled = true
half_life_days = 7

[[admins]]
platform = "qq"
user_id = "987654"
```

</details>

## 配置说明

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `tags` | 内置 4 套 | 关系标签字典，可修改提示词模板、说话倍率与好感度基准 |
| `people` | `[]` | 人物名单，支持多标签和标记其他 Bot |
| `group_sets` | `[]` | 公共集合定义，成员可写 QQ 群号、`private:QQ号` 或 `user:QQ号` |
| `affinity.enabled` | `true` | 动态好感度开关，群聊与私聊分开计算 |
| `affinity.stranger_weight` | `0.85` | 未在名单内用户的默认发言倍率 |
| `admins` | `[]` | 高级设置：管理命令鉴权名单，其他插件默认继承此名单 |

## 命令与工具

| 类别 | 名称 / 格式 | 说明 |
|---|---|---|
| 管理命令 | `/关系 + <QQ号> <标签1,标签2>` | 添加或更新指定用户的人物标签 |
| 管理命令 | `/关系 bot <QQ号> <主人称呼> <角色>` | 快捷标记其他 Bot 及其归属 |
| 管理命令 | `/关系` 或 `/关系 列表` | 列出当前已登记的关系条目 |
| 管理命令 | `/关系 - <QQ号>` | 删除记录（支持对静态配置条目软删除） |
| 对话工具 | `query_circle_relation(user)` | 按称呼或账号查询未在最近上下文出现的联系人信息 |
| WebUI 控件 | `运行状态与生效范围` / `重置好感度` | 查看熟人、Bot 数量与近期好感度变化，或重置好感度进度 |

<details>
<summary>开发与自检</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

</details>
