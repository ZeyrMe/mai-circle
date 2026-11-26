# 群关系

`zeyr.mai-circle` · 人工关系与同行 Bot 归属。

开发基线 MaiBot 1.4.8 / SDK 2.23.0。可独立安装，其他 zeyr 插件仅通过公开 API 自动联动。

首批已实现：人工静态关系、同行 Bot 归属、独立的对话层 Master 人设、管理员鉴权、关系持久化、`is_bot`/`is_admin`/`filter_humans`/`get_mentions_context` API、`query_circle_relation` 工具，以及 EARLY 关系提示。管理员名单只用于程序鉴权，不进入提示词；动态画像仍交给宿主记忆系统。

可用 `/关系 + <user_id> <relation_tag>` 追加关系。缺少本插件时其他插件会降级，不会阻止加载；本插件也可以单独运行。

仍需在已升级的真实 MaiBot 1.4.8 宿主上做 Hook/组件验收，当前离线测试不等同于生产上线。

安装时将整个目录同步到宿主 plugins；运行 config.toml 由 SDK 生成。实例名单、个人资料和密钥只填运行配置，不提交。

检查：`python -m pytest`，开发依赖见 pyproject.toml。
