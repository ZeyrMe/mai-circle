from conftest import module


def make(**config):
    plugin = module.Plugin()
    plugin.set_plugin_config({"plugin": {"config_version": "0.1.0"}, **config})
    return plugin


async def test_admin_identity_and_conversation_persona_are_independent():
    plugin = make(
        admins=[{"platform": "qq", "user_id": "SECRET_ADMIN"}],
        people=[{"platform": "qq", "user_id": "friend", "name": "朋友", "persona_master": True}],
    )
    assert (await plugin.api_admin("qq", "SECRET_ADMIN"))["data"]["value"]
    assert not (await plugin.api_admin("other", "SECRET_ADMIN"))["data"]["value"]
    assert not (await plugin.api_admin("qq", "friend"))["data"]["value"]
    text = plugin.context("qq", ["SECRET_ADMIN", "friend"])
    assert "SECRET_ADMIN" not in text
    assert "最铁的老熟人" in text


async def test_bot_filter_keeps_unknown_humans_and_separates_platforms():
    plugin = make(people=[{"platform": "qq", "user_id": "bot", "is_bot": True}])
    messages = [
        {"platform": platform, "message_info": {"user_info": {"user_id": user}}}
        for platform, user in [("qq", "bot"), ("qq", "human"), ("other", "bot")]
    ]
    data = (await plugin.api_humans(messages))["data"]["messages"]
    assert data == messages[1:]


async def test_disabled_does_not_claim_admin_or_inject():
    plugin = make(enabled=False, admins=[{"platform": "qq", "user_id": "admin"}])
    assert not plugin.is_admin("qq", "admin")
    assert plugin.context("qq", ["admin"]) == ""


def test_relations_persist_separately_from_config(tmp_path):
    store = module.StateFile(tmp_path / "relations.json", {"schema_version": 1, "people": []})
    plugin = make()
    plugin.store = store
    store.data["people"].append({"platform": "qq", "user_id": "a", "name": "朋友", "relation_tag": "同学"})
    store.save()
    reloaded = make()
    reloaded.store = module.StateFile(store.path, {"schema_version": 1, "people": []})
    assert "同学" in reloaded.context("qq", ["a"])
