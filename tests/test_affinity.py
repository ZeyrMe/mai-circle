import importlib

from conftest import module

Affinity = importlib.import_module(module.__package__ + ".affinity").Affinity


def test_logarithmic_quality_saturation_decay_and_scope_separation():
    config = module.Config().affinity
    state = Affinity()
    key = ("qq", "u", "group")
    for i in range(15):
        state.observe(key, str(i), True, config, now=100)
    saturated = state.offset(key, config, now=100)
    for i in range(15, 300):
        state.observe(key, str(i), True, config, now=100)
    assert state.offset(key, config, now=100) == saturated
    assert abs(state.offset(key, config, now=100 + 7 * 86400) - saturated / 2) < 1e-8
    assert state.offset(("qq", "u", "private"), config, now=100) == 0
    before = state.rows[key].copy()
    state.observe(key, "299", True, config, now=100)
    assert state.rows[key] == before


async def test_multitag_weight_relax_and_bot_deweight_are_configured():
    plugin = module.Plugin()
    plugin.set_plugin_config(
        {
            "plugin": {"config_version": "0.1.0"},
            "people": [
                {"user_id": "friend", "name": "朋友", "tags": ["老熟人", "损友"]},
                {"user_id": "bot", "is_bot": True, "tags": ["老熟人"]},
            ],
        }
    )
    weight = (await plugin.api_weight("qq", ["friend"]))["data"]
    assert abs(weight["weight"] - 1.17) < 1e-8
    assert weight["relax_bonus"] > 0
    assert (await plugin.api_weight("qq", ["bot"]))["data"]["weight"] == 0.5
    assert "老熟人" in plugin.context("qq", ["friend"])
    assert "损友" in plugin.context("qq", ["friend"])
