from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator

from .ecosystem import ScopeConfig, anchor


class TagDef(PluginConfigBase):
    tag: str = Field(
        default="",
        description="关系标签名字，例如 老熟人、损友、同行Bot。",
        json_schema_extra={"label": "标签名", "placeholder": "写唯一的标签名，如：老熟人、游戏搭子"},
    )
    prompt_template: str = Field(
        default="{name}：{tag} {custom_note}",
        description="给这个标签的人写一句说话感觉提示。",
        json_schema_extra={
            "label": "标签语气提示",
            "placeholder": "写对这类人的语气提示；可用 {name} 称呼、{custom_note} 备注、{owner_name} 归属",
        },
    )
    base_affinity: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="这个关系天然的亲疏基准（0 到 1）。",
        json_schema_extra={"label": "基础亲疏度"},
    )
    weight_multiplier: float = Field(
        default=1,
        ge=0.1,
        le=2,
        description="和这类人聊天时的说话意愿倍率。",
        json_schema_extra={"label": "搭话意愿倍率"},
    )
    privacy_relax: float = Field(
        default=0,
        ge=0,
        le=1,
        description="面对这类人追问隐私兜着项时，额外放宽的松口幅度。",
        json_schema_extra={"label": "松口加成"},
    )


def default_tags():
    return [
        TagDef(
            tag="普通群友",
            prompt_template="{name}：群里常聊的朋友 {custom_note}",
            base_affinity=0.5,
            weight_multiplier=1.0,
        ),
        TagDef(
            tag="老熟人",
            prompt_template="{name}：很熟的老朋友，聊起来自在放松就行 {custom_note}",
            base_affinity=0.8,
            weight_multiplier=1.22,
            privacy_relax=0.25,
        ),
        TagDef(
            tag="损友",
            prompt_template="{name}：熟到能互相吐槽开玩笑的损友 {custom_note}",
            base_affinity=0.7,
            weight_multiplier=1.12,
            privacy_relax=0.15,
        ),
        TagDef(
            tag="同行Bot",
            prompt_template="{name}：{owner_name}家的{bot_role}，正常搭话调侃但别互相复读 {custom_note}",
            base_affinity=0.5,
            weight_multiplier=0.5,
        ),
    ]


class AffinityConfig(PluginConfigBase):
    """根据近期真实有效的互动，在人工标签锚点附近柔和微调亲疏感与搭话积极度。刷水话不涨分，长期不聊会自动回到人工设定基准；群聊和私聊分开统计。"""

    enabled: bool = Field(
        default=True,
        description="开启后温和随近期互动波动搭话意愿，关闭则死守标签里的固定基准。",
        json_schema_extra={
            "label": "启用热络度",
            "order": 1,
            "hint": "不会出现数值刷爆或掉成陌生人的问题，始终围绕人工锚点小幅摆动。",
        },
    )
    timezone: str = Field(
        default="Asia/Shanghai",
        description="单日增益的本地时区",
        json_schema_extra={"label": "统计时区", "hidden": True},
    )
    active_hint: str = Field(
        default="最近聊得挺热乎",
        description="近期互动明显升温时，附在关系提示后的短语。",
        json_schema_extra={
            "label": "热络提示语",
            "order": 2,
            "placeholder": "例如：最近经常聊到一起",
            "hint": "需开启下方的“提示里带上热络语”才会在对话提示里露出。",
        },
    )
    show_dynamic_hint: bool = Field(
        default=False,
        description="开启后，关系近期升温时会把上面那句短语带进对话提示里。",
        json_schema_extra={
            "label": "提示里带上热络语",
            "order": 3,
            "hint": "默认关闭以保持关系提示克制不冗长；打开后最近聊得热的人会带上热络提示。",
        },
    )
    half_life_days: float = Field(
        default=7,
        gt=0,
        le=365,
        description="多久没怎么聊之后，升温出来的热络感会减半回落。",
        json_schema_extra={
            "label": "回落半衰期（天）",
            "order": 4,
            "hint": "单位：天（默认 7）。几天不联系后多余的热度逐步消退，最终停在标签自带的“基础亲疏度”。",
        },
    )
    day_gain: float = Field(
        default=0.04,
        ge=0,
        le=0.2,
        description="单日对数增益系数",
        json_schema_extra={"label": "单日增益上限", "hidden": True},
    )
    quality_saturation: float = Field(
        default=15,
        ge=1,
        le=100,
        description="每天有效回合饱和数",
        json_schema_extra={"label": "单日有效饱和数", "hidden": True},
    )
    min_text_chars: int = Field(
        default=4,
        ge=1,
        le=100,
        description="有效文本最短字数",
        json_schema_extra={"label": "有效消息字数", "hidden": True},
    )
    window_minutes: float = Field(
        default=10,
        gt=0,
        le=1440,
        description="近期发言的人在几分钟内继续影响当前聊天氛围权重。",
        json_schema_extra={
            "label": "氛围延续分钟",
            "order": 5,
            "hint": "单位：分钟（默认 10）。老熟人说话后的这几分钟内，整个群聊都会维持略高的回复意愿。",
        },
    )
    max_entries: int = Field(
        default=1024,
        ge=1,
        le=10000,
        description="动态联系人状态上限",
        json_schema_extra={"label": "状态缓存上限", "hidden": True},
    )
    seen_messages: int = Field(
        default=2048,
        ge=1,
        le=10000,
        description="消息去重上限",
        json_schema_extra={"label": "消息去重上限", "hidden": True},
    )
    min_weight: float = Field(
        default=0.5,
        ge=0.1,
        le=1,
        description="关系加权后最低降到的倍率。",
        json_schema_extra={
            "label": "权重下限",
            "order": 6,
            "hint": "默认 0.50（保留对同行 Bot 的半倍降权，不和同伴 Bot 无限互刷）。",
        },
    )
    max_weight: float = Field(
        default=1.3,
        ge=1,
        le=2,
        description="关系加权后最高抬到的倍率。",
        json_schema_extra={
            "label": "权重上限",
            "order": 7,
            "hint": "默认 1.30。建议不超过 1.5，避免老熟人出现后把群变话痨。",
        },
    )
    dynamic_weight_scale: float = Field(
        default=0.3,
        ge=0,
        le=1,
        description="动态偏移对频率的影响",
        json_schema_extra={"label": "动态调权幅度", "hidden": True},
    )
    stranger_weight: float = Field(
        default=0.85,
        ge=0.1,
        le=2,
        description="完全没在熟人名单里的人说话时使用的默认搭话倍率。",
        json_schema_extra={
            "label": "路人默认倍率",
            "order": 8,
            "hint": "默认 0.85。熟人标签通常设在 1.1–1.2，和路人 0.85 搭配后群聊平均说话频率刚好稳定在宿主原设值附近。",
        },
    )
    fallback_frequency_enabled: bool = Field(
        default=True,
        description="没装麦的一天时，由本插件直接接管关系倍率调整。",
        json_schema_extra={
            "label": "独立调节频率",
            "order": 9,
            "hint": "若同时装了「麦的一天」，本插件会自动让位给麦的一天做统一乘法合成。",
        },
    )
    tick_seconds: float = Field(
        default=30,
        ge=5,
        le=300,
        description="频率协调后台周期",
        json_schema_extra={"label": "协调周期秒数", "hidden": True},
    )


class Person(PluginConfigBase):
    platform: str = Field(
        default="qq",
        description="所在平台，QQ 保持默认即可。",
        json_schema_extra={"label": "平台", "placeholder": "默认填 qq"},
    )
    user_id: str = Field(
        default="",
        description="对方的 QQ 号或平台账号。",
        json_schema_extra={"label": "用户账号", "placeholder": "必填，直接填对方 QQ 号（如 987654）"},
    )
    name: str = Field(
        default="",
        description="平时怎么称呼对方。",
        json_schema_extra={"label": "称呼", "placeholder": "Bot 怎么叫对方，如：阿云、老板、小Q"},
    )
    tags: list[str] = Field(
        default_factory=list,
        description="贴一个或多个上面定义过的标签名。",
        json_schema_extra={
            "label": "关系标签",
            "placeholder": "写标签字典里已有的标签（可多个），如：老熟人、损友",
        },
    )
    relation_tag: str = Field(
        default="",
        description="旧版单标签兼容字段。",
        json_schema_extra={"label": "兼容旧标签", "hidden": True},
    )
    is_bot: bool = Field(
        default=False,
        description="如果是群里的其他 Bot，请勾上。",
        json_schema_extra={"label": "是同行 Bot"},
    )
    owner_name: str = Field(
        default="",
        description="仅同行 Bot 填写：这是谁家的 Bot。",
        json_schema_extra={
            "label": "谁家的 Bot",
            "placeholder": "非 Bot 留空；同行 Bot 写主人称呼，如：阿明",
        },
    )
    bot_role: str = Field(
        default="",
        description="仅同行 Bot 填写：它大致是什么角色。",
        json_schema_extra={
            "label": "Bot 定位",
            "placeholder": "非 Bot 留空；同行 Bot 写定位，如：群管、点歌机",
        },
    )
    custom_note: str = Field(
        default="",
        description="补充一点关于这个人的硬备注。",
        json_schema_extra={"label": "补充备注", "placeholder": "选填一句话硬备注，如：经常熬夜、不爱听剧透"},
    )
    persona_master: bool = Field(
        default=False,
        description="对话层老熟人标记（只影响聊天亲切感，不开放管理命令权限）。",
        json_schema_extra={"label": "对话老熟人"},
    )


class GroupSet(PluginConfigBase):
    name: str = Field(
        default="",
        description="给一组常一起用的群或人起个外号。",
        json_schema_extra={
            "label": "集合名称",
            "placeholder": "取个简短集合名，如：观察群、熟人群（别处写 @set:观察群 引用）",
        },
    )
    members: list[str] = Field(
        default_factory=list,
        description="包含的群号或用户账号。",
        json_schema_extra={
            "label": "包含成员",
            "placeholder": "QQ 群直接填群号（如 123456）；私聊写 private:QQ号；按人写 user:QQ号",
        },
    )

    @field_validator("members")
    @classmethod
    def validate_members(cls, values):
        for value in values:
            anchor(value)
        return list(dict.fromkeys(values))


class Admin(PluginConfigBase):
    platform: str = Field(
        default="qq", description="平台名称。", json_schema_extra={"label": "平台", "placeholder": "默认 qq"}
    )
    user_id: str = Field(
        default="",
        description="有权使用管理命令的账号。",
        json_schema_extra={
            "label": "管理员账号",
            "placeholder": "填拥有管理员权限的 QQ 号（仅代码鉴权，永不放进聊天里）",
        },
    )


class PluginInfo(PluginConfigBase):
    config_version: str = Field(default="0.1.0", description="配置版本，由 Runner 管理")


class Config(PluginConfigBase):
    scope: ScopeConfig = Field(default_factory=ScopeConfig, description="独立控制哪些群或人启用群关系")
    show_advanced: bool = Field(
        default=False,
        description="展开管理员名单、提示上限与高阶参数。",
        json_schema_extra={
            "label": "显示高级设置",
            "order": 6,
            "hint": "新增或修改管理命令鉴权人、调整多人同框提示字数时勾选展开。",
        },
    )
    plugin: PluginInfo = Field(default_factory=PluginInfo)
    enabled: bool = Field(
        default=True,
        description="开启后识别名单内的熟人与同行 Bot。",
        json_schema_extra={
            "label": "启用群关系",
            "order": 1,
            "hint": "不会代替宿主的动态记忆画像，只管“硬标定关系 + 同行 Bot 过滤 + 公共集合”。",
        },
    )
    tags: list[TagDef] = Field(
        default_factory=default_tags,
        description="先定义好每种关系标签对应的语气提示和说话倍率。",
        json_schema_extra={
            "label": "关系标签字典",
            "order": 2,
            "hint": "已内置普通群友/老熟人/损友/同行Bot 四套自然模板，建议直接改提示词适配人设；想加“群主”“学姐”等新标签直接点添加，模板可用 {name} {custom_note} {owner_name} {bot_role}。",
        },
    )
    affinity: AffinityConfig = Field(default_factory=AffinityConfig)
    group_sets: list[GroupSet] = Field(
        default_factory=list,
        description="维护常用的群/私聊合集，方便其余插件直接用 @set:名称 一处复用。",
        json_schema_extra={
            "label": "公共集合",
            "order": 4,
            "hint": "强烈建议把常用的“观察群”“核心熟人群”建在这里，之后在其余 5 个插件的范围框里填 @set:集合名 就能一改全改。",
        },
    )
    people: list[Person] = Field(
        default_factory=list,
        description="登记熟人、群友或同行 Bot。",
        json_schema_extra={
            "label": "人物名单",
            "order": 3,
            "hint": "每条必填「用户账号 + 称呼 + 关系标签」；如果是群里的其他 Bot，务必勾选“是同行 Bot”并填“谁家的 Bot”与“Bot 定位”，见闻和生活插件会自动屏蔽同行 Bot 防互刷。",
        },
    )
    admins: list[Admin] = Field(
        default_factory=list,
        description="有权执行 /关系、/待办、/日程、/唤醒、/总结 等管理命令的账号。",
        json_schema_extra={
            "label": "管理命令鉴权名单",
            "hint": "纯代码层权限校验名单，永远不会写入大模型上下文；“麦的一天 / 日历 / 见闻”未单独配管理员时也会自动继承这里的名单。",
        },
    )
    master_persona_hint: str = Field(
        default="最铁的老熟人",
        description="旧版老熟人提示兼容模板。",
        json_schema_extra={"label": "兼容熟人短语", "hidden": True},
    )
    relation_template: str = Field(
        default="{name}：{relation_tag} {custom_note}",
        description="旧版关系模板兼容字段。",
        json_schema_extra={"label": "兼容关系模板", "hidden": True},
    )
    bot_template: str = Field(
        default="{name}：{owner_name}家的{bot_role}；{custom_note}",
        description="旧版同行 Bot 模板兼容字段。",
        json_schema_extra={"label": "兼容同行模板", "hidden": True},
    )
    master_template: str = Field(
        default="{name}：{master_persona_hint}",
        description="旧版熟人模板兼容字段。",
        json_schema_extra={"label": "兼容熟人模板", "hidden": True},
    )
    hint_chars: int = Field(
        default=100,
        ge=0,
        le=200,
        description="多人同时出现时注入关系提示的最大总字数。",
        json_schema_extra={
            "label": "关系提示字数上限",
            "hint": "默认 100 字。人多且备注较长时可适当上调到 120–160，避免末尾人物被截断。",
        },
    )

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


_BASIC_FIELDS = ["enabled", "tags", "people", "group_sets", "show_advanced"]
for _name, _field in Config.model_fields.items():
    if _name not in _BASIC_FIELDS and _name != "plugin":
        _field.json_schema_extra = {
            **(_field.json_schema_extra or {}),
            "depends_on": "show_advanced",
            "depends_value": True,
        }
Config.model_rebuild(force=True)

for _model in list(globals().values()):
    if isinstance(_model, type) and issubclass(_model, PluginConfigBase):
        for _field_name, _field_info in _model.model_fields.items():
            _field_info.json_schema_extra = {
                "label": _field_info.description or _field_name,
                **(_field_info.json_schema_extra or {}),
            }
        _model.model_rebuild(force=True)
