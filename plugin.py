import asyncio
import contextlib
import math
import time
from typing import Any

from maibot_sdk import API, Command, HookHandler, MaiBotPlugin, Tool
from maibot_sdk.config_widgets import ConfigWidget, ConfigWidgetState
from maibot_sdk.types import HookOrder, ToolParameterInfo

from .affinity import Affinity
from .config_models import Config, Person
from .ecosystem import ChatIdentity, EcosystemMixin, anchor
from .runtime import RecentMessages, StateFile, identity, inject, optional_api, render, result, service_send


class Plugin(EcosystemMixin, MaiBotPlugin):
    config_model = Config
    config_widgets = EcosystemMixin.config_widgets + [
        ConfigWidget(
            id="reset_affinity",
            kind="action",
            label="重置动态热络度",
            confirmation="将所有动态热络度恢复到人工锚点？",
        ),
    ]

    def __init__(self):
        super().__init__()
        self.recent = RecentMessages()
        self.store = None
        self.affinity = Affinity()
        self.frequency_routes = {}
        self.stream_users = {}
        self.frequency_owned = {}
        self.task = None
        self.day_seen = False

    async def on_load(self):
        self.store = StateFile(
            self.ctx.paths.data_dir / "relations.json", {"schema_version": 1, "people": []}
        )
        for row in self.store.data.get("affinity", []):
            key = (row["platform"], row["user_id"], row["scope_kind"])
            self.affinity.rows[key] = row["state"]
        self.task = asyncio.create_task(self.frequency_loop(), name="circle-frequency")

    async def on_unload(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        await self.restore_frequency()
        self.persist_affinity()
        self.recent = RecentMessages()

    async def on_config_update(self, scope, config_data, version):
        pass

    def people(self):
        configured = {(person.platform, person.user_id): person for person in self.config.people}
        for raw in self.store.data["people"] if self.store else []:
            person = Person.model_validate(raw)
            configured[(person.platform, person.user_id)] = person
        deleted = set((self.store.data.get("deleted") or []) if self.store else [])
        return (
            [person for (platform, uid), person in configured.items() if f"{platform}:{uid}" not in deleted]
            if self.config.enabled
            else []
        )

    def is_admin(self, platform, user_id):
        return self.config.enabled and any(
            p.platform == platform and p.user_id == user_id for p in self.config.admins
        )

    def context(self, platform, user_ids, scope_kind="group"):
        if not self.config.enabled:
            return ""
        lines = []
        for person in self.people():
            if person.platform != platform or person.user_id not in user_ids:
                continue
            values = person.model_dump()
            values["master_persona_hint"] = self.config.master_persona_hint
            template = self.config.bot_template if person.is_bot else self.config.relation_template
            definitions = [tag for tag in self.config.tags if tag.tag in person.tags]
            if definitions:
                lines.extend(
                    render(tag.prompt_template, **values, tag=tag.tag).strip() for tag in definitions
                )
            else:
                lines.append(render(template, **values).strip())
            if person.is_bot and definitions:
                lines.append(render(self.config.bot_template, **values).strip())
            if (
                self.config.affinity.show_dynamic_hint
                and self.affinity.offset((platform, person.user_id, scope_kind), self.config.affinity) > 0
            ):
                lines.append(self.config.affinity.active_hint)
            if person.persona_master:
                lines.append(render(self.config.master_template, **values).strip())
        return "；".join(lines)

    def resolve_scope_ref(self, ref):
        data = {"groups": [], "privates": [], "users": []}
        if not self.config.enabled:
            return data
        if ref.startswith("@set:"):
            members = next((row.members for row in self.config.group_sets if row.name == ref[5:]), [])
        elif ref.startswith("@tag:"):
            members = [
                f"{person.platform}:user:{person.user_id}"
                for person in self.people()
                if ref[5:] in person.tags or ref[5:] == person.relation_tag
            ]
        else:
            return data
        for member in members:
            platform, kind, value = anchor(member)
            key = {"group": "groups", "private": "privates", "user": "users"}[kind]
            data[key].append(f"{platform}:{kind}:{value}")
        return data

    @API("resolve_scope_ref", public=True, version="1")
    async def api_scope_ref(self, ref: str, **kwargs):
        return result(self.resolve_scope_ref(ref))

    def console_text(self):
        people = self.people()
        active = sorted(
            self.affinity.rows, key=lambda key: self.affinity.offset(key, self.config.affinity), reverse=True
        )[:5]
        names = {(person.platform, person.user_id): person.name or "已标定联系人" for person in people}
        kind_labels = {"group": "群聊", "private": "私聊"}
        top = [
            f"{names.get(key[:2], '未标定联系人')}（{kind_labels.get(key[2], key[2])}热络 +{self.affinity.offset(key, self.config.affinity):.2f}）"
            for key in active
            if self.affinity.offset(key, self.config.affinity) > 0
        ]
        return (
            f"已登记联系人：{sum(not row.is_bot for row in people)} 位熟人 · {sum(row.is_bot for row in people)} 个同行 Bot · {len(self.config.group_sets)} 个公共集合（管理员名单永不入对话）\n"
            + (f"近期热络升温：{'；'.join(top)}" if top else "近期热络升温：暂无明显升温（都在基准线上）")
        )

    def weight(self, platform, user_ids, scope_kind="group"):
        now = time.time()
        values = []
        for uid in dict.fromkeys(user_ids):
            person = next(
                (row for row in self.people() if row.platform == platform and row.user_id == uid), None
            )
            tags = [
                tag
                for tag in self.config.tags
                if person and (tag.tag in person.tags or tag.tag == person.relation_tag)
            ]
            base_weight = (
                sum(tag.weight_multiplier for tag in tags) / len(tags)
                if tags
                else self.config.affinity.stranger_weight
            )
            relax = sum(tag.privacy_relax for tag in tags) / len(tags) if tags else 0
            base = sum(tag.base_affinity for tag in tags) / len(tags) if tags else 0.5
            if person and person.is_bot:
                base_weight = min(
                    base_weight,
                    next(
                        (tag.weight_multiplier for tag in self.config.tags if tag.tag == "同行Bot"),
                        base_weight,
                    ),
                )
            key = (platform, uid, scope_kind)
            offset = self.affinity.offset(key, self.config.affinity) if self.config.affinity.enabled else 0
            offset = min(1 - base, offset)
            row = self.affinity.rows.get(key)
            decay = math.exp2(-(now - row["at"]) / (self.config.affinity.window_minutes * 60)) if row else 0
            values.append((base_weight + offset * self.config.affinity.dynamic_weight_scale, relax, decay))
        total = sum(row[2] for row in values)
        if total:
            weight = sum(row[0] * row[2] for row in values) / total
            relax = sum(row[1] * row[2] for row in values) / total
        elif values:
            weight, relax = values[-1][:2]
        else:
            weight, relax = 1, 0
        return {
            "weight": max(self.config.affinity.min_weight, min(self.config.affinity.max_weight, weight)),
            "relax_bonus": relax,
        }

    @API("get_chat_weight", public=True, version="1")
    async def api_weight(self, platform="qq", user_ids=None, scope_kind="group", **kwargs):
        if scope_kind not in ("group", "private"):
            return result(error="scope_kind 应为 group / private")
        return result(
            self.weight(platform, user_ids or [], scope_kind)
            if self.config.enabled
            else {"weight": 1, "relax_bonus": 0}
        )

    async def frequency_tick(self):
        async with asyncio.timeout(0.4):
            self.day_seen = bool(await self.ctx.api.get("zeyr.mai-day.get_state", version="1"))
        self.persist_affinity()
        if not self.config.enabled or not self.config.affinity.fallback_frequency_enabled:
            await self.restore_frequency()
            return
        for stream, chat in list(self.frequency_routes.items()):
            if not await self.target_in_scope(chat.platform, chat.group_id, chat.user_id, stream):
                await self.restore_frequency(stream)
                continue
            owner = (
                await optional_api(self.ctx, "zeyr.mai-day.get_state", stream_id=stream)
                if self.day_seen
                else None
            )
            if self.day_seen and (
                owner is None or owner.get("frequency_owner", owner.get("phase") != "disabled")
            ):
                await self.restore_frequency(stream)
                continue
            cutoff = time.time() - self.config.affinity.window_minutes * 60
            ids = [uid for uid, stamp in self.stream_users.get(stream, {}).items() if stamp >= cutoff]
            desired = self.weight(chat.platform, ids, chat.kind)["weight"]
            response = await self.ctx.frequency.get_adjust(stream)
            if not isinstance(response, dict) or not response.get("success"):
                continue
            previous = self.frequency_owned.get(stream)
            original = previous[0] if previous else float(response["value"])
            sent = await self.ctx.frequency.set_adjust(stream, desired)
            if isinstance(sent, dict) and sent.get("success"):
                self.frequency_owned[stream] = (original, desired)

    async def frequency_loop(self):
        await asyncio.sleep(3)
        while True:
            try:
                await self.frequency_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.ctx.logger.exception("关系频率协调失败，下轮重试")
            await asyncio.sleep(self.config.affinity.tick_seconds)

    def persist_affinity(self):
        if self.store:
            self.store.data["affinity"] = [
                {"platform": key[0], "user_id": key[1], "scope_kind": key[2], "state": row}
                for key, row in self.affinity.rows.items()
            ]
            self.store.save()

    async def restore_frequency(self, only=None):
        for stream, (original, written) in list(self.frequency_owned.items()):
            if only and stream != only:
                continue
            with contextlib.suppress(Exception):
                current = await self.ctx.frequency.get_adjust(stream)
                if current.get("success") and math.isclose(float(current["value"]), written):
                    await self.ctx.frequency.set_adjust(stream, original)
            self.frequency_owned.pop(stream, None)

    async def get_config_widget_state(self):
        return {**await super().get_config_widget_state(), "reset_affinity": ConfigWidgetState()}

    async def on_config_widget_action(self, action_id):
        if action_id == "reset_affinity":
            self.affinity = Affinity()
            return
        await super().on_config_widget_action(action_id)

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
        return result({"context": self.context(platform, user_ids, kwargs.get("scope_kind", "group"))})

    @Tool(
        "query_circle_relation",
        description="查人工标记的熟人关系或同行归属，不代替动态记忆画像。",
        parameters=[ToolParameterInfo(name="user", description="人物称呼或平台用户标识")],
        visibility="visible",
    )
    async def query_relation(self, user: str, platform: str = "qq", **kwargs):
        if not await self.in_scope(**kwargs):
            return result(error="当前会话不在插件生效范围")
        ids = [p.user_id for p in self.people() if p.platform == platform and user in (p.user_id, p.name)]
        return result({"context": self.context(platform, ids)})

    @Command("relation", pattern=r"^/关系\s*\+\s*(?P<user>\S+)\s+(?P<tag>.+)$")
    async def relation(self, message=None, matched_groups=None, stream_id="", **kwargs):
        if not await self.in_scope(message, stream_id=stream_id):
            return False, "当前会话不在插件生效范围", 1
        platform, user, _, _ = identity(message or {})
        if not self.is_admin(platform, user):
            return False, "需要管理员权限", 1
        try:
            groups = matched_groups or {}
            person = Person(
                platform=platform,
                user_id=groups["user"],
                name=groups["user"],
                relation_tag=groups["tag"],
                tags=[tag.strip() for tag in groups["tag"].split(",") if tag.strip()],
            )
            if not person.user_id:
                raise ValueError("缺少 user_id")
            rows = self.store.data["people"]
            rows[:] = [p for p in rows if (p["platform"], p["user_id"]) != (person.platform, person.user_id)]
            rows.append(person.model_dump(mode="json"))
            self.store.data["deleted"] = [
                key for key in self.store.data.get("deleted", []) if key != f"{platform}:{person.user_id}"
            ]
            self.store.save()
        except (ValueError, KeyError) as exc:
            return False, str(exc), 1
        await service_send(
            self.ctx,
            "关系已记录",
            stream_id,
        )
        return True, "关系已记录", 2

    @Command("relation_list", pattern=r"^/关系\s*(?:列表)?$")
    async def relation_list(self, message=None, stream_id="", **kwargs):
        platform, uid, _, _ = identity(message or {})
        if not await self.in_scope(message, stream_id=stream_id) or not self.is_admin(platform, uid):
            return False, "需要管理员权限及有效范围", 1
        text = (
            "\n".join(
                f"{person.user_id} {person.name} {','.join(person.tags) or person.relation_tag}"
                for person in self.people()
                if person.platform == platform
            )
            or "暂无人工关系"
        )
        await service_send(self.ctx, text, stream_id)
        return True, text, 2

    @Command("relation_delete", pattern=r"^/关系\s*-\s*(?P<user>\S+)$")
    async def relation_delete(self, message=None, matched_groups=None, stream_id="", **kwargs):
        platform, uid, _, _ = identity(message or {})
        if not await self.in_scope(message, stream_id=stream_id) or not self.is_admin(platform, uid):
            return False, "需要管理员权限及有效范围", 1
        user = str((matched_groups or {}).get("user") or "")
        if not user:
            return False, "需要人物标识", 1
        self.store.data.setdefault("deleted", []).append(f"{platform}:{user}")
        self.store.data["people"] = [
            row for row in self.store.data["people"] if (row["platform"], row["user_id"]) != (platform, user)
        ]
        self.store.save()
        await service_send(self.ctx, "关系已删除", stream_id)
        return True, "关系已删除", 2

    @Command("relation_bot", pattern=r"^/关系\s+bot\s+(?P<user>\S+)\s+(?P<owner>\S+)\s+(?P<role>.+)$")
    async def relation_bot(self, message=None, matched_groups=None, stream_id="", **kwargs):
        platform, uid, _, _ = identity(message or {})
        if not await self.in_scope(message, stream_id=stream_id) or not self.is_admin(platform, uid):
            return False, "需要管理员权限及有效范围", 1
        groups = matched_groups or {}
        if not all(groups.get(key) for key in ("user", "owner", "role")):
            return False, "需要同行标识、归属称呼和角色", 1
        person = Person(
            platform=platform,
            user_id=groups["user"],
            name=groups["user"],
            is_bot=True,
            owner_name=groups["owner"],
            bot_role=groups["role"],
            tags=["同行Bot"],
        )
        self.store.data["people"] = [
            row
            for row in self.store.data["people"]
            if (row["platform"], row["user_id"]) != (platform, person.user_id)
        ] + [person.model_dump(mode="json")]
        self.store.data["deleted"] = [
            key for key in self.store.data.get("deleted", []) if key != f"{platform}:{person.user_id}"
        ]
        self.store.save()
        await service_send(self.ctx, "同行归属已记录", stream_id)
        return True, "同行归属已记录", 2

    @HookHandler("chat.receive.after_process")
    async def remember(self, message=None, **kwargs):
        if self.config.enabled and await self.in_scope(message, **kwargs):
            self.recent.add(message or {})
            chat = ChatIdentity.from_message(message)
            text = str((message or {}).get("processed_plain_text") or "").strip()
            if chat.stream_id and chat.user_id:
                self.frequency_routes[chat.stream_id] = chat
                users = self.stream_users.setdefault(chat.stream_id, {})
                users[chat.user_id] = time.time()
                cutoff = time.time() - self.config.affinity.window_minutes * 60 * 3
                self.stream_users[chat.stream_id] = {
                    uid: stamp for uid, stamp in users.items() if stamp >= cutoff
                }
                self.stream_users = dict(
                    list(self.stream_users.items())[-self.config.scope.max_tracked_streams :]
                )
                self.frequency_routes = dict(
                    list(self.frequency_routes.items())[-self.config.scope.max_tracked_streams :]
                )
                # Incoming questions/addressed messages/private turns count; pure group chatter does not.
                quality = len(text) >= self.config.affinity.min_text_chars and (
                    chat.kind == "private"
                    or "?" in text
                    or "？" in text
                    or bool((message or {}).get("is_mentioned") or (message or {}).get("is_at"))
                )
                self.affinity.observe(
                    (chat.platform, chat.user_id, chat.kind),
                    str((message or {}).get("message_id") or ""),
                    quality,
                    self.config.affinity,
                )
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
                        str(data.get("target_user_id") or data.get("user_id", ""))
                        if isinstance(data, dict)
                        else str(data)
                    )
        return "；".join(self.context(platform, ids) for platform, ids in by_platform.items())

    @HookHandler("maisaka.planner.before_request", order=HookOrder.EARLY)
    async def planner(self, **kwargs):
        if not await self.in_scope(**kwargs):
            return {"action": "continue"}
        return inject(kwargs, "mai-circle", self.hint(kwargs), self.config.hint_chars)

    @HookHandler("maisaka.replyer.before_request", order=HookOrder.EARLY)
    async def replyer(self, **kwargs):
        if not await self.in_scope(**kwargs):
            return {"action": "continue"}
        return inject(kwargs, "mai-circle", self.hint(kwargs), self.config.hint_chars)


def create_plugin():
    return Plugin()
