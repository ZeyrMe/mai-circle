from typing import Any

from maibot_sdk import API, Command, HookHandler, MaiBotPlugin, Tool
from maibot_sdk.types import HookOrder, ToolParameterInfo

from .config_models import Config, Person
from .runtime import RecentMessages, StateFile, identity, inject, render, result


class Plugin(MaiBotPlugin):
    config_model = Config

    def __init__(self):
        super().__init__()
        self.recent = RecentMessages()
        self.store = None

    async def on_load(self):
        self.store = StateFile(
            self.ctx.paths.data_dir / "relations.json", {"schema_version": 1, "people": []}
        )

    async def on_unload(self):
        self.recent = RecentMessages()

    async def on_config_update(self, scope, config_data, version):
        pass

    def people(self):
        configured = {(person.platform, person.user_id): person for person in self.config.people}
        for raw in self.store.data["people"] if self.store else []:
            person = Person.model_validate(raw)
            configured[(person.platform, person.user_id)] = person
        return list(configured.values()) if self.config.enabled else []

    def is_admin(self, platform, user_id):
        return self.config.enabled and any(
            p.platform == platform and p.user_id == user_id for p in self.config.admins
        )

    def context(self, platform, user_ids):
        if not self.config.enabled:
            return ""
        lines = []
        for person in self.people():
            if person.platform != platform or person.user_id not in user_ids:
                continue
            values = person.model_dump()
            values["master_persona_hint"] = self.config.master_persona_hint
            template = self.config.bot_template if person.is_bot else self.config.relation_template
            lines.append(render(template, **values).strip())
            if person.persona_master:
                lines.append(render(self.config.master_template, **values).strip())
        return "；".join(lines)

    @API("is_bot", public=True, version="1")
    async def api_bot(self, platform: str, user_id: str, **kwargs):
        return result(
            {
                "value": any(
                    p.platform == platform and p.user_id == user_id and p.is_bot for p in self.people()
                )
            }
        )

    @API("is_admin", public=True, version="1")
    async def api_admin(self, platform: str, user_id: str, **kwargs):
        return result({"value": self.is_admin(platform, user_id)})

    @API("filter_humans", public=True, version="1")
    async def api_humans(self, messages: list[dict], **kwargs):
        bots = {(p.platform, p.user_id) for p in self.people() if p.is_bot}
        return result({"messages": [message for message in messages if identity(message)[:2] not in bots]})

    @API("get_mentions_context", public=True, version="1")
    async def api_context(self, user_ids: list[str], platform: str = "qq", **kwargs):
        return result({"context": self.context(platform, user_ids)})

    @Tool(
        "query_circle_relation",
        description="查人工标记的熟人关系或同行归属，不代替动态记忆画像。",
        parameters=[ToolParameterInfo(name="user", description="人物称呼或平台用户标识")],
        visibility="visible",
    )
    async def query_relation(self, user: str, platform: str = "qq", **kwargs):
        ids = [p.user_id for p in self.people() if p.platform == platform and user in (p.user_id, p.name)]
        return result({"context": self.context(platform, ids)})

    @Command("relation", pattern=r"^/关系\s*\+\s*(?P<user>\S+)\s+(?P<tag>.+)$")
    async def relation(self, message=None, matched_groups=None, stream_id="", **kwargs):
        platform, user, _, _ = identity(message or {})
        if not self.is_admin(platform, user):
            return False, "需要管理员权限", 1
        try:
            groups = matched_groups or {}
            person = Person(
                platform=platform, user_id=groups["user"], name=groups["user"], relation_tag=groups["tag"]
            )
            if not person.user_id:
                raise ValueError("缺少 user_id")
            rows = self.store.data["people"]
            rows[:] = [p for p in rows if (p["platform"], p["user_id"]) != (person.platform, person.user_id)]
            rows.append(person.model_dump(mode="json"))
            self.store.save()
        except (ValueError, KeyError) as exc:
            return False, str(exc), 1
        await self.ctx.send.text("关系已记录", stream_id)
        return True, "关系已记录", 2

    @HookHandler("chat.receive.after_process")
    async def remember(self, message=None, **kwargs):
        if self.config.enabled:
            self.recent.add(message or {})
        return {"action": "continue"}

    def hint(self, kwargs: dict[str, Any]):
        messages = self.recent.matched(kwargs)
        by_platform = {}
        for message in messages:
            platform, uid, _, _ = identity(message)
            by_platform.setdefault(platform, set()).add(uid)
            for component in (
                message.get("raw_message", []) if isinstance(message.get("raw_message"), list) else []
            ):
                if component.get("type") in ("at", "mention"):
                    data = component.get("data") or {}
                    by_platform[platform].add(
                        str(data.get("user_id", "")) if isinstance(data, dict) else str(data)
                    )
        return "；".join(self.context(platform, ids) for platform, ids in by_platform.items())

    @HookHandler("maisaka.planner.before_request", order=HookOrder.EARLY)
    async def planner(self, **kwargs):
        return inject(kwargs, "mai-circle", self.hint(kwargs), self.config.hint_chars)

    @HookHandler("maisaka.replyer.before_request", order=HookOrder.EARLY)
    async def replyer(self, **kwargs):
        return inject(kwargs, "mai-circle", self.hint(kwargs), self.config.hint_chars)


def create_plugin():
    return Plugin()
