from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator

from .ecosystem import ScopeConfig, anchor


class TagDef(PluginConfigBase):
    tag: str = Field(default="", description="唯一标签名")
    prompt_template: str = Field(default="{name}：{tag} {custom_note}", description="关系提示模板")
    base_affinity: float = Field(default=0.5, ge=0, le=1, description="人工热络度锚点")
    weight_multiplier: float = Field(default=1, ge=0.1, le=2, description="回复意愿权重")
    privacy_relax: float = Field(default=0, ge=0, le=1, description="松口加成")


def default_tags():
    return [
        TagDef(tag="普通群友", base_affinity=0.5, weight_multiplier=1.0),
        TagDef(tag="老熟人", base_affinity=0.8, weight_multiplier=1.22, privacy_relax=0.25),
        TagDef(tag="损友", base_affinity=0.7, weight_multiplier=1.12, privacy_relax=0.15),
        TagDef(tag="同行Bot", base_affinity=0.5, weight_multiplier=0.5),
    ]


class AffinityConfig(PluginConfigBase):
    __ui_label__ = "动态热络度"
    enabled: bool = Field(default=True, description="启用温和动态热络度")
    timezone: str = Field(default="Asia/Shanghai", description="单日增益的本地时区")
    active_hint: str = Field(default="最近聊得热络", description="可选动态热络提示")
    show_dynamic_hint: bool = Field(default=False, description="在关系上下文附加简短热络状态")
    half_life_days: float = Field(default=7, gt=0, le=365, description="回归人工锚点半衰期")
    day_gain: float = Field(default=0.04, ge=0, le=0.2, description="单日对数增益系数")
    quality_saturation: float = Field(default=15, ge=1, le=100, description="每天有效回合饱和数")
    min_text_chars: int = Field(default=4, ge=1, le=100, description="有效文本最短字数")
    window_minutes: float = Field(default=10, gt=0, le=1440, description="近期参与权重半衰期")
    max_entries: int = Field(default=1024, ge=1, le=10000, description="动态联系人状态上限")
    seen_messages: int = Field(default=2048, ge=1, le=10000, description="消息去重上限")
    min_weight: float = Field(default=0.5, ge=0.1, le=1, description="权重下限，保留同行 Bot 降权")
    max_weight: float = Field(default=1.3, ge=1, le=2, description="权重上限")
    dynamic_weight_scale: float = Field(default=0.3, ge=0, le=1, description="动态偏移对频率的影响")
    stranger_weight: float = Field(default=0.85, ge=0.1, le=2, description="未标定用户基础权重")
    fallback_frequency_enabled: bool = Field(default=True, description="未启用 mai-day 时写入关系频率")
    tick_seconds: float = Field(default=30, ge=5, le=300, description="频率协调后台周期")


class Person(PluginConfigBase):
    platform: str = Field(default="qq", description="平台")
    user_id: str = Field(default="", description="平台用户标识")
    name: str = Field(default="", description="称呼")
    tags: list[str] = Field(default_factory=list, description="一人可挂多个标签")
    relation_tag: str = Field(default="", description="人工关系标签")
    is_bot: bool = Field(default=False, description="同行 Bot")
    owner_name: str = Field(default="", description="归属人物称呼")
    bot_role: str = Field(default="", description="同行角色")
    custom_note: str = Field(default="", description="人工备注")
    persona_master: bool = Field(default=False, description="对话中的老熟人；与管理员身份无关")


class GroupSet(PluginConfigBase):
    name: str = Field(default="", description="公共集合名称；以 @set:名称 引用")
    members: list[str] = Field(
        default_factory=list, description="group/private/user 对象；可含平台前缀，不嵌套集合"
    )

    @field_validator("members")
    @classmethod
    def validate_members(cls, values):
        for value in values:
            anchor(value)
        return list(dict.fromkeys(values))


class Admin(PluginConfigBase):
    platform: str = Field(default="qq", description="平台")
    user_id: str = Field(default="", description="管理员用户标识")


class PluginInfo(PluginConfigBase):
    config_version: str = Field(default="0.1.0", description="配置版本，由 Runner 管理")


class Config(PluginConfigBase):
    scope: ScopeConfig = Field(default_factory=ScopeConfig, description="独立会话与用户生效范围")
    show_advanced: bool = Field(default=False, description="显示高级设置")
    plugin: PluginInfo = Field(default_factory=PluginInfo)
    enabled: bool = Field(default=True, description="启用插件")
    tags: list[TagDef] = Field(default_factory=default_tags, description="标签定义与提示词字典")
    affinity: AffinityConfig = Field(default_factory=AffinityConfig)
    group_sets: list[GroupSet] = Field(default_factory=list, description="全生态复用的公共会话和用户集合")
    people: list[Person] = Field(default_factory=list, description="人工静态关系")
    admins: list[Admin] = Field(default_factory=list, description="程序鉴权名单，不进入 Prompt")
    master_persona_hint: str = Field(default="最铁的老熟人", description="对话层熟人提示")
    relation_template: str = Field(default="{name}：{relation_tag} {custom_note}", description="关系渲染")
    bot_template: str = Field(
        default="{name}：{owner_name}家的{bot_role}；{custom_note}", description="同行渲染"
    )
    master_template: str = Field(default="{name}：{master_persona_hint}", description="熟人渲染")
    hint_chars: int = Field(default=100, ge=0, le=200, description="关系提示最大字数")

    @model_validator(mode="after")
    def unique_sets(self):
        names = [item.name.strip() for item in self.group_sets]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("公共集合名称不能为空或重复")
        tags = [row.tag for row in self.tags]
        if any(not tag for tag in tags) or len(tags) != len(set(tags)):
            raise ValueError("标签名称不能为空或重复")
        if self.affinity.min_weight > self.affinity.max_weight:
            raise ValueError("热络度权重下限不能超过上限")
        return self


# SDK 2.23 supports conditional fields; keep the first-use form small.
_BASIC_FIELDS = ["enabled", "tags", "people", "group_sets", "show_advanced"]
for _name, _field in Config.model_fields.items():
    if _name not in _BASIC_FIELDS and _name != "plugin":
        _field.json_schema_extra = {
            **(_field.json_schema_extra or {}),
            "depends_on": "show_advanced",
            "depends_value": True,
        }
Config.model_rebuild(force=True)


# SDK labels otherwise fall back to Python field names in top-level sections.
for _model in list(globals().values()):
    if isinstance(_model, type) and issubclass(_model, PluginConfigBase):
        for _field_name, _field_info in _model.model_fields.items():
            _field_info.json_schema_extra = {
                "label": _field_info.description or _field_name,
                **(_field_info.json_schema_extra or {}),
            }
        _model.model_rebuild(force=True)
