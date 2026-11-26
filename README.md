<div align="center">

# 群关系 · `zeyr.mai-circle`

**帮 Bot 分清群里谁是熟人、谁是谁家的 Bot，并集中维护全生态共享的好友集合**

![Version](https://img.shields.io/badge/version-0.2.0-brightgreen)
![MaiBot](https://img.shields.io/badge/MaiBot-1.4.8%2B-2f81f7)
![SDK](https://img.shields.io/badge/SDK-2.23.0-0e8a16)
![Standalone](https://img.shields.io/badge/独立运行-支持-blue)

[为什么用它](#为什么用它) · [3 步快速开始](#3-步快速开始) · [配置项说明](#常用配置项说明) · [命令与控制台](#命令工具与控制台) · [FAQ](#常见疑问)

</div>

---

## 为什么用它

| 常见问题 | 传统做法的困扰 | **群关系（`zeyr.mai-circle`）** |
|---|---|---|
| 群里其他 Bot 互聊刷屏 | 全靠记忆模块自己猜，经常跟同行 Bot 无限复读或学进脏黑话 | 显式标出 `is_bot = true` 及主人归属，自动降权防互刷，并通知见闻/爬楼跳过它们 |
| 主人/管理员身份破防 | 把管理员写进人设说“这是你主人”，一聊天就露馅承认自己是 Bot | **`admins` 仅程序鉴权永不进 Prompt**，对话层只给熟人标签与自然语气引导 |
| 线性好感度被水群刷爆 | 聊一句 +1 分，水群一天直接变死党、几天不说话又归零 | 采用**单日对数饱和 + 7 天半衰期回锚点**，围绕人工标签基准温和起伏 |
| 黑白名单复制粘贴 6 遍 | 6 个插件分别填一模一样的观察群、熟人群号 | 在此维护一份 `公共集合`，其余插件直接写 `@set:集合名` 统一生效 |

---

## 3 步快速开始

### WebUI 上手（推荐）
1. 将 `mai-circle/` 放入宿主 `plugins/` 并重启，打开 **群关系** 配置页。
2. 在 **人物名单** 点添加：填好熟人和群里同行 Bot 的 QQ 号、称呼和标签（群里 Bot 务必勾选 **是同行 Bot** 并写上“谁家的 Bot”）。
3. 在 **公共集合** 建好常用集合（比如取名 `观察群`，填入群号），其他插件的范围框就能直接填 `@set:观察群`。

<details>
<summary>手改 config.toml 示例（附完整注释）</summary>

```toml
enabled = true

[[group_sets]]
name = "观察群"
members = ["111222333"]                              # 别处用 @set:观察群 引用

[[people]]
user_id = "987654"
name = "阿云"
tags = ["老熟人"]                                    # 支持一人挂多个标签字典里的标签
persona_master = true                                # 只影响聊天熟络感，不授予管理员命令权限
custom_note = "经常半夜写代码"

[[people]]
user_id = "654321"
name = "小Q"
is_bot = true
tags = ["同行Bot"]
owner_name = "阿明"                                  # 同行 Bot 专属：谁家的谁
bot_role = "群管"

[affinity]
enabled = true
half_life_days = 7                                   # 几天不聊后多余热度逐步回到锚点

[[admins]]
platform = "qq"
user_id = "987654"                                   # 仅程序命令鉴权，永不进入大模型上下文
```

</details>

---

## 常用配置项说明

| 配置项 | 默认值 | 怎么填与效果说明 |
|---|---|---|
| `tags` | 内置 4 套 | 标签字典：每类可单独改 `prompt_template` 语气、`base_affinity`、`weight_multiplier` 说话倍率与 `privacy_relax` 松口加成 |
| `people` | `[]` | 人工标定的人或 Bot；可填多标签，`is_bot` 会同时参与过滤其它插件消息 |
| `group_sets` | `[]` | 公共集合；成员可直接填 QQ 群号，或写 `private:QQ号` / `user:QQ号`，不支持集合嵌套 |
| `affinity.enabled` | `true` | 温和动态热络度总开关（群聊与私聊分开计算）；关闭后固定按标签基准执行 |
| `affinity.stranger_weight` | `0.85` | 未进名单的普通路人发言时的基础权重，与熟人 `1.1–1.2` 平衡整体群发言期望 |
| `admins` | `[]` | 高级区：允许在聊天里执行管理命令的账号；其余 `zeyr.*` 插件也会自动继承 |

---

## 命令、工具与控制台

### 群/私聊管理命令（需在 `admins` 内）
| 命令 | 作用 |
|---|---|
| `/关系 + <QQ号> <标签1,标签2>` | 动态添加或更新某个人的关系标签 |
| `/关系 bot <QQ号> <主人称呼> <角色定位>` | 快捷标记同行 Bot 与归属 |
| `/关系` 或 `/关系 列表` | 查看当前已登记的全部关系条目 |
| `/关系 - <QQ号>` | 删除记录（支持对静态配置条目软删除） |

### 对话工具与 WebUI 控件
- **工具 `query_circle_relation(user)`**：聊起不在场的第三人时按需查询（在场活跃发言人已在 `EARLY` 自动注入，无需重复查）。
- **WebUI 控制台**：`运行状态与生效范围`（展示熟人/Bot/集合计数与近期升温联系人）+ `重置动态热络度`（二次确认）。

---

## 生态联动与常见疑问

- **联动关系**：在无 `mai-day` 时按 `affinity.fallback_frequency_enabled` 独立调节群聊频率；同装 `mai-day` 时自动让位给 `mai-day` 统一合成；为 `mai-insights` / `mai-day` 提供同行 Bot 过滤，为全生态解析 `@set:` / `@tag:`。
- **Q：会和 MaiBot 原生 A-Memorix 记忆打架吗？**
  不会。本插件只管人工标定的客观关系和温和倍率，具体聊天内容与长期印象仍由宿主原生记忆系统处理。

<details>
<summary>开发、门禁与安全审计</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

</details>
