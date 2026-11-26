from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator

from .ecosystem import ScopeConfig, anchor


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
    group_sets: list[GroupSet] = Field(default_factory=list, description="全生态复用的公共会话和用户集合")
    people: list[Person] = Field(default_factory=list, description="人工静态关系")
    admins: list[Admin] = Field(default_factory=list, description="程序鉴权名单，不进入 Prompt")
    master_persona_hint: str = Field(default="最铁的老熟人", description="对话层熟人提示")
    relation_template: str = Field(default="{name}：{relation_tag} {custom_note}", description="关系渲染")
    bot_template: str = Field(
        default="{name}：{owner_name}家的{bot_role}；{custom_note}", description="同行渲染"
    )
    master_template: str = Field(default="{name}：{master_persona_hint}", description="熟人渲染")
    hint_chars: int = Field(default=55, ge=0, le=120, description="关系提示最大字数")

    @model_validator(mode="after")
    def unique_sets(self):
        names = [item.name.strip() for item in self.group_sets]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("公共集合名称不能为空或重复")
        return self


# SDK 2.23 supports conditional fields; keep the first-use form small.
_BASIC_FIELDS = ["enabled", "master_persona_hint", "people", "show_advanced"]
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
