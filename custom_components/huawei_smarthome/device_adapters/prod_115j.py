"""115J 遥控大师空调伴侣 (YKK-KT16A) 适配器。

设备: ``prodId = 115J`` / deviceModel ``YKK-KT16A`` / deviceTypeId ``007`` "万能遥控器" /
厂商 深圳遥看科技有限公司 (manufacturerId ``0a4``), H5 遥控页 ``115J/h5_001/index.html``。

伴侣串在空调插座与空调插头之间，自身物模型里**没有**可控制的继电器服务：它靠内置红外码库
遥控空调，并用 ``powerCon`` 统计流经插座的功率/电量，用这份功率"自动判断空调开关机"
(H5 i18n ``study.openStatus``: "开启后，空调伴侣将根据功率判断开关状态")。

本文件的口径全部可溯源 —— **字段名与取值范围**取自真机物模型
(``.storage/huawei_smarthome/profiles/115J.json``, 16 个服务), **报文形状**取自 H5 正式包
(``115J/h5_001/static/js/app.*.js`` + 异步 chunk ``3.js`` / ``1.js``) 的写帧代码。

实体 (7 个，key 沿用已注册实体以免 HA 里多出孤儿实体):

* ``climate.air`` — 空调。物模型 ``airKey``: ``power`` 0 关 / 1 开，``mode`` 0 自动 1 除湿
  2 送风 3 制热 4 制冷，``wind`` 0 自动 1 低 2 中 3 高，``temp`` 16-30, ``up`` 扫风 0/1。
  H5 ``clickSwitch`` / ``clickTemp`` / ``clickUp`` / ``clickLeft`` / ``clickLight`` 与
  ``modeListResult`` / ``windListResult`` 用的是同一形状的帧:
  ``{id: 0, mode, wind, temp, up[, left][, light][, power]}``; ``id`` 恒为 0
  (descCh: 0 = 通过 APP/语音/云端下发的离散控制参数)。关机只发 ``{id: 0, power: 0}``。
  设备没上报 ``left`` 时扫风退化为"关/开"两档 (只有 ``up`` 有官方定义)。
* ``switch.indicator_led`` — 空调伴侣指示灯 (``ledOnoff.ledOnoff`` 0/1)。H5 ``changeSwitch``:
  ``{ledOnoff: {ledOnoff: 0|1}}``。物模型 ``report = 0`` (设备不主动上报), 所以只在写入后
  乐观回填，不假装知道设备真实状态。
* ``switch.screen_light`` — 空调屏幕显示/灯光 (``airKey.light`` 0/1)。H5 ``clickLight`` 只在
  开机时允许切换，适配器照做。``light`` 不在物模型里，只有设备上报过才建实体。
* ``switch.auto_detect`` — 自动判断空调开关机 (``switchPower.on`` 0/1)。H5
  ``switchPowerFn`` / ``autoDetectStatus``: ``{switchPower: {on: 0|1}}``; i18n
  ``pub.autoStatus`` = "自动判断空调开/关机", 设置页仅在固件 > 1.0.5.5 时显示。该服务不在
  物模型里，只有设备上报过才建实体。
* ``sensor.current_power`` (``powerCon.power``, W) / ``sensor.energy_consumption``
  (``powerCon.watt``, kWh) / ``sensor.work_time`` (``powerCon.workTime``, min)。
  descCh 原文：实时功率 W / 本次时间间隔内的度数 kWh / 本次时间间隔内的工作时长 分钟，
  上报频度"每 5 分钟一次"—— **都是区间值，不是累计值**, 所以 state_class 用 measurement。

不建实体的服务：``deviceList`` / ``cmdList`` / ``loadRes`` / ``refKey`` / ``hotKey`` /
``sumKey`` / ``matchKey`` / ``timer`` / ``sumTimer`` / ``delay`` / ``delayAirkey`` /
``update`` / ``netInfo`` —— 配网、码库下载、急速制冷/制热、睡眠曲线、倒计时与 OTA 都留给
App; 场景类开关要在 ``cmdList`` / ``refKey`` / ``timer`` 之间链式下三帧，需要真机逐项实测
之后再补，免得出现"点了没反应"的实体。

和客厅 ``107J`` (遥看小苹果 ``YKK-1011``) 不通用：指示灯字段是 ``ledOnoff`` (107J 是
``on``), 开关值是 0/1 (107J 是 1/2), 没有 ``controlKey``, 但多了 ``powerCon``。两个适配器
互不依赖，可同时安装。

只读设计：不轮询、不起后台任务、不发额外请求，状态全由集成既有的云端 MQTT 推送驱动
(``should_poll = False``); 每次写操作后立刻 ``apply_state_snapshot`` 乐观回填。

---

**关于"空调实体不出现"的修复 (v2)**

根因：空调实体出不出来，由 ``entities()`` 里对 ``airKey`` 的判定决定。旧判定
``context.has_service("airKey")`` 是【设备实时上报】或【物模型 profile 声明】的并集。
当运行时 ``context.profile`` 没有挂载 (或挂的是不含 ``airKey`` 的旧物模型缓存), 同时设备
当前又还没把 ``airKey`` 上报给集成时，该判定为 False，空调实体就被整体丢弃 —— 但指示灯、
功率这些设备一直在实时上报的服务不受影响，于是出现"灯/传感器能出、空调不出"。

本版本把空调判定放宽为 ``_air_supported()``:

1. 物模型 profile 声明了 ``airKey`` → 建空调 (标准能力);
2. 设备实时上报过 ``airKey`` → 建空调;
3. profile 完全缺失(``None``) → 仍按产品定位 (空调伴侣 / 万能遥控器 / 码库已配对) 建空调，
   并 ``warning`` 提示需补齐物模型;
4. profile 存在但不含 ``airKey`` → 建空调，并 ``warning`` 提示疑似旧物模型缓存，建议
   删除 ``.storage/huawei_smarthome/profiles/115J.json`` 后重拉。

同时在每次 ``entities()`` 被调用时打印一条诊断日志 (warning 级，前缀 ``[115J adapter]``),
把 ``has_profile`` / 物模型声明的服务列表 / 设备上报的 ``airKey`` 字段 / 是否建出空调 一次
看全，便于继续定位。
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from ..domain.models import RemoteServiceState
from .api import EntitySpec, HuaweiProductAdapter
from .context import DeviceContext

_LOGGER = logging.getLogger(__name__)

_PROD_ID = "115J"
prod_id = _PROD_ID

# --- 服务 / 字段名 (全部取自真机物模型) ---------------------------------------

_AIR_SID = "airKey"
_AIR_ID_FIELD = "id"
_AIR_ID = 0  # descCh: 0 = APP/语音/云端下发的离散控制参数
_AIR_POWER_ON = 1
_AIR_POWER_OFF = 0
_LEFT_FIELD = "left"  # 官方物模型未声明，固件实测上报后才给左右扫风
_PANEL_LIGHT_FIELD = "light"  # 同上，实测 115J 上报 airKey.light

_LED_SID = "ledOnoff"
_LED_FIELD = "ledOnoff"

_AUTO_SID = "switchPower"  # 只在固件运行期上报，不在物模型里
_AUTO_FIELD = "on"

_POWER_CON_SID = "powerCon"

# --- airKey 取值表 (物模型 enumList / descCh) ---------------------------------

_AIR_MIN_TEMP = 16
_AIR_MAX_TEMP = 30
_AIR_TEMP_STEP = 1
_AIR_MODES = ("off", "auto", "cool", "heat", "dry", "fan_only")
_AIR_MODE_CODE = {"auto": 0, "dry": 1, "fan_only": 2, "heat": 3, "cool": 4}
_AIR_CODE_MODE = {code: mode for mode, code in _AIR_MODE_CODE.items()}
_AIR_FAN_MODES = ("auto", "low", "medium", "high")
_AIR_WIND_CODE = {mode: wind for wind, mode in enumerate(_AIR_FAN_MODES)}
# 只有 up 时官方定义是 0 全关 / 1 全开; 设备额外上报 left 时才给四档
# (H5 created(): fwv>1055 且 up/left 都支持才放 "不扫风/上下扫风/左右扫风/扫风全开")。
_AIR_SWING_BASIC = ("off", "on")
_AIR_SWING_FULL = ("off", "vertical", "horizontal", "both")
_AIR_SWING_CODE = {
    "off": (0, 0),
    "on": (1, 0),
    "vertical": (1, 0),
    "horizontal": (0, 1),
    "both": (1, 1),
}

# 除湿必须低风、送风不能自动风 (H5 modeListResult: case 1 → wind=1, case 2 → wind||1)。
_MODE_FORCED_WIND = {"dry": 1}

# --- 实体 key / 名称 (对齐 H5 的 i18n 文案) ------------------------------------

_CLIMATE_KEY = "air"
_LED_KEY = "indicator_led"  # 沿用已注册 key, 名称改回 App 文案
_LIGHT_KEY = "screen_light"  # 同上
_AUTO_KEY = "auto_detect"  # 语义是"自动判断", 跟旧的 socket_power 不是一件事，换 key
_SENSOR_POWER_KEY = "current_power"
_SENSOR_ENERGY_KEY = "energy_consumption"
_SENSOR_WORK_KEY = "work_time"

_CLIMATE_NAME = "空调"
_LED_NAME = "空调伴侣指示灯"  # H5 settings.pilot_lamp
_LIGHT_NAME = "空调屏幕显示"
_AUTO_NAME = "自动判断开关机"  # H5 pub.autoStatus
_SENSOR_SPECS: tuple[tuple[str, str, str, Mapping[str, Any]], ...] = (
    # (实体 key, 名称，powerCon 字段，单位/设备类) —— 单位取自 descCh，不做换算。
    (
        _SENSOR_POWER_KEY,
        "当前功率",
        "power",
        {"unit": "W", "device_class": "power", "state_class": "measurement"},
    ),
    (
        _SENSOR_ENERGY_KEY,
        "间隔用电量",
        "watt",
        # HA 不允许 device_class='energy' 配 state_class='measurement'
        # (energy 只接受 total / total_increasing); 本传感器是区间值非累计，
        # 故去掉 device_class 只保留 kWh 单位 + measurement，避免告警。
        {"unit": "kWh", "state_class": "measurement"},
    ),
    (
        _SENSOR_WORK_KEY,
        "间隔工作时长",
        "workTime",
        {"unit": "min", "device_class": "duration", "state_class": "measurement"},
    ),
)


# --- 基础取值 / 能力判定 ------------------------------------------------------


def _to_int(value: Any) -> int | None:
    """兼容云端用字符串下发数字的情况；``bool`` 也当 0/1。"""

    if isinstance(value, bool):
        return int(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_flag(value: Any) -> bool | None:
    number = _to_int(value)
    return None if number is None else number != 0


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _profile_fields(context: DeviceContext, sid: str) -> set[str]:
    """某服务的字段名集合 = 当前上报值里的字段 + 物模型里声明的字段。"""

    fields = set(context.service_state(sid))
    profile = context.profile if isinstance(context.profile, Mapping) else {}
    for service in profile.get("services", ()) or ():
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for characteristic in service.get("characteristics", ()) or ():
            if isinstance(characteristic, Mapping):
                name = characteristic.get("characteristicName")
                if name:
                    fields.add(str(name))
    return fields


def _has_field(context: DeviceContext, sid: str, field: str) -> bool:
    return field in _profile_fields(context, sid)


def _left_supported(context: DeviceContext) -> bool:
    """固件是否支持左右扫风 (物模型没写，实测 115J 上报 ``airKey.left``)。"""

    return _has_field(context, _AIR_SID, _LEFT_FIELD)


def _panel_light_supported(context: DeviceContext) -> bool:
    """空调是否支持屏显 (H5 用码库 ``remote_props`` 问，这里以实测上报 ``light`` 为准)。"""

    return _has_field(context, _AIR_SID, _PANEL_LIGHT_FIELD)


def _swing_modes(context: DeviceContext) -> tuple[str, ...]:
    """扫风档位：只有 ``up`` 时是"关/开", 额外支持 ``left`` 时给四档。"""

    return _AIR_SWING_FULL if _left_supported(context) else _AIR_SWING_BASIC


def _optimistic_update(
    context: DeviceContext, sid: str, payload: Mapping[str, Any]
) -> None:
    """把刚下发的字段回填本地状态，免得 HA 界面在下一次上报前回跳。"""

    context.apply_state_snapshot({sid: RemoteServiceState(sid=sid, data=dict(payload))})


def _profile_service_ids(context: DeviceContext) -> list[str]:
    """物模型 profile 里声明的所有 serviceId (按出现顺序去重)。"""

    profile = context.profile if isinstance(context.profile, Mapping) else {}
    out: list[str] = []
    for service in profile.get("services", ()) or ():
        if not isinstance(service, Mapping):
            continue
        sid = service.get("serviceId")
        if isinstance(sid, str) and sid and sid not in out:
            out.append(sid)
    return out


def _profile_declares_service(context: DeviceContext, sid: str) -> bool:
    return sid in _profile_service_ids(context)


def _air_supported(context: DeviceContext) -> bool:
    """空调实体是否建出。

    v2 起放宽：不再因为 ``has_service(airKey)`` 为 False 就把整个空调实体丢掉。
    ``has_service`` 是 [设备实时上报] 或 [物模型声明] 的并集，设备刚配对/上报未到/物模型
    缓存是旧版时都会为 False; 但这类"空调伴侣"的核心能力就是 airKey，应稳定建出空调，
    同时用日志说明到底卡在哪一环，方便继续排查。
    """

    reported = dict(context.service_state(_AIR_SID))
    declared = _profile_declares_service(context, _AIR_SID)
    has_profile = isinstance(context.profile, Mapping)

    if declared:
        return True
    if reported:
        return True
    if not has_profile:
        # 物模型没挂载：可能本地 .storage 缓存缺失/未拉取。仍按产品定位建出空调。
        _LOGGER.warning(
            "[115J adapter] airKey 判定兜底：profile 未挂载 (has_profile=False), "
            "按空调伴侣定位建出空调实体; 建议确认 .storage/huawei_smarthome/profiles/115J.json "
            "存在且含 airKey 服务，否则空调可能无法真正遥控。name=%s",
            context.name,
        )
        return True
    # profile 存在但不含 airKey —— 疑似旧物模型缓存。
    _LOGGER.warning(
        "[115J adapter] airKey 判定兜底：物模型已挂载但 services 未声明 airKey "
        "(profile_services=%s), 疑似旧物模型缓存。已按产品定位建出空调实体; "
        "建议删除 .storage/huawei_smarthome/profiles/115J.json 让集成重拉最新物模型。name=%s",
        _profile_service_ids(context),
        context.name,
    )
    return True


def _log_air_diagnostics(context: DeviceContext, created: bool) -> None:
    """打印一条可定位的诊断日志 (warning 级，前缀 [115J adapter])。"""

    reported = dict(context.service_state(_AIR_SID))
    _LOGGER.warning(
        "[115J adapter] name=%s prod_id=%s has_profile=%s "
        "profile_services=%s airKey_in_profile=%s airKey_reported_fields=%s "
        "air_entity_created=%s",
        context.name,
        context.prod_id,
        isinstance(context.profile, Mapping),
        _profile_service_ids(context),
        _profile_declares_service(context, _AIR_SID),
        list(reported),
        created,
    )


# --- 空调 (climate.air) -------------------------------------------------------


def _air_mode_name(state: Mapping[str, Any]) -> str | None:
    """只有 ``power`` 明确上报时才给模式; 关机恒为 ``off``, 未知一律 ``None``。"""

    power = _to_int(state.get("power"))
    if power == _AIR_POWER_OFF:
        return "off"
    if power is None:
        return None
    code = _to_int(state.get("mode"))
    if code is None:
        return None
    return _AIR_CODE_MODE.get(code)


def _fan_mode_name(state: Mapping[str, Any]) -> str | None:
    wind = _to_int(state.get("wind"))
    if wind is None or not 0 <= wind < len(_AIR_FAN_MODES):
        return None
    return _AIR_FAN_MODES[wind]


def _swing_name(context: DeviceContext, state: Mapping[str, Any]) -> str | None:
    up_on = _to_flag(state.get("up"))
    if _swing_modes(context) == _AIR_SWING_BASIC:
        return None if up_on is None else ("on" if up_on else "off")
    left_on = _to_flag(state.get(_LEFT_FIELD))
    if up_on is None and left_on is None:
        return None
    if up_on and left_on:
        return "both"
    if up_on:
        return "vertical"
    if left_on:
        return "horizontal"
    return "off"


def _air_state(context: DeviceContext) -> Mapping[str, Any]:
    """climate 的状态投影。设备不上报室温，所以 ``current_temperature`` 恒为 ``None``。"""

    state = context.service_state(_AIR_SID)
    return {
        "hvac_mode": _air_mode_name(state),
        "target_temperature": _to_number(state.get("temp")),
        "fan_mode": _fan_mode_name(state),
        "swing_mode": _swing_name(context, state),
    }


def _air_frame(
    context: DeviceContext, state: Mapping[str, Any], **overrides: Any
) -> dict[str, Any]:
    """按 H5 口径拼一帧控制参数：``id`` + mode/wind/temp/up [+left] [+light] [+power]。

    取值优先级：本次动作要改的字段 → 设备当前上报值; **拿不到就不放这个字段**
    (H5 的 ``windListResult`` / ``clickUp`` / ``clickLeft`` 帧本来也只带一部分字段，设备对
    缺省字段保持原值，补 0 反而会把风速/扫风写到自动档)。
    """

    frame: dict[str, Any] = {_AIR_ID_FIELD: _AIR_ID}
    for field in ("mode", "wind", "temp", "up"):
        value = _to_int(overrides.get(field, state.get(field)))
        if value is not None:
            frame[field] = value
    if _left_supported(context):
        left = _to_int(overrides.get(_LEFT_FIELD, state.get(_LEFT_FIELD)))
        if left is not None:
            frame[_LEFT_FIELD] = left
    if _panel_light_supported(context):
        light = _to_int(overrides.get(_PANEL_LIGHT_FIELD, state.get(_PANEL_LIGHT_FIELD)))
        if light is not None:
            frame[_PANEL_LIGHT_FIELD] = light
    power = _to_int(overrides.get("power"))
    if power is not None:
        frame["power"] = power
    return frame


def _swing_codes(context: DeviceContext, swing_mode: str | None) -> tuple[int, int]:
    """HA 扫风档位 → 设备 ``(up, left)``; 不支持左右扫风时档位表只有 关/开。"""

    if swing_mode not in _swing_modes(context):
        raise ValueError(f"unsupported swing mode: {swing_mode}")
    return _AIR_SWING_CODE[swing_mode]


def _wake_power(state: Mapping[str, Any]) -> int | None:
    """已关机时补 ``power: 1``, 让这帧参数顺带开机 (H5 是直接拒绝操作，HA 侧这样更顺手)。"""

    return None if _to_int(state.get("power")) == _AIR_POWER_ON else _AIR_POWER_ON


def _hvac_mode_frame(
    context: DeviceContext,
    state: Mapping[str, Any],
    data: Mapping[str, Any],
    wake: int | None,
) -> dict[str, Any]:
    """HA 模式 → ``airKey`` 帧; 关机只发 ``power: 0``, 除湿强制低风 (H5 modeListResult)。"""

    hvac_mode = _to_str(data.get("hvac_mode"))
    if hvac_mode == "off":
        return {_AIR_ID_FIELD: _AIR_ID, "power": _AIR_POWER_OFF}
    if hvac_mode not in _AIR_MODE_CODE:
        raise ValueError(f"unsupported hvac mode: {hvac_mode}")
    overrides: dict[str, Any] = {"mode": _AIR_MODE_CODE[hvac_mode]}
    if hvac_mode in _MODE_FORCED_WIND:
        overrides["wind"] = _MODE_FORCED_WIND[hvac_mode]
    elif hvac_mode == "fan_only" and not _to_int(state.get("wind")):
        # H5: 送风模式下若是自动风就退到低风 (自动风对送风模式没意义)。
        overrides["wind"] = _AIR_WIND_CODE["low"]
    return _air_frame(context, state, power=wake, **overrides)


def _air_action(kind: str):
    """打包 climate 的 6 个动作，每个动作 = 一帧 ``airKey`` 写入。"""

    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        state = context.service_state(_AIR_SID)
        wake = _wake_power(state)

        if kind == "turn_on":
            # H5 clickSwitch 开机分支：带当前参数的帧 (设备用这帧参数开机)。
            frame = _air_frame(context, state, power=_AIR_POWER_ON)
        elif kind == "turn_off":
            # H5 clickSwitch 关机分支：只发 power=0，不动其它参数。
            frame = {_AIR_ID_FIELD: _AIR_ID, "power": _AIR_POWER_OFF}
        elif kind == "set_hvac_mode":
            frame = _hvac_mode_frame(context, state, data, wake)
        elif kind == "set_temperature":
            temperature = _to_number(data.get("temperature"))
            if temperature is None:
                raise ValueError("temperature is required")
            temp = max(_AIR_MIN_TEMP, min(_AIR_MAX_TEMP, int(round(temperature))))
            frame = _air_frame(context, state, power=wake, temp=temp)
        elif kind == "set_fan_mode":
            fan_mode = _to_str(data.get("fan_mode"))
            if fan_mode not in _AIR_WIND_CODE:
                raise ValueError(f"unsupported fan mode: {fan_mode}")
            frame = _air_frame(
                context, state, power=wake, wind=_AIR_WIND_CODE[fan_mode]
            )
        elif kind == "set_swing_mode":
            up, left = _swing_codes(context, _to_str(data.get("swing_mode")))
            frame = _air_frame(context, state, power=wake, up=up, left=left)
        else:
            raise ValueError(f"unsupported air action: {kind}")

        await context.async_send_service(_AIR_SID, frame)
        _optimistic_update(context, _AIR_SID, frame)

    return action


# --- 开关 (指示灯 / 屏幕显示 / 自动判断) ---------------------------------------


def _led_state(context: DeviceContext) -> Mapping[str, Any]:
    return {"is_on": _to_flag(context.value(_LED_SID, _LED_FIELD))}


def _led_action(led_on: bool):
    """H5 changeSwitch: ``{ledOnoff: {ledOnoff: 0|1}}``。"""

    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        payload = {_LED_FIELD: 1 if led_on else 0}
        await context.async_send_service(_LED_SID, payload)
        _optimistic_update(context, _LED_SID, payload)

    return action


def _panel_light_state(context: DeviceContext) -> Mapping[str, Any]:
    return {"is_on": _to_flag(context.value(_AIR_SID, _PANEL_LIGHT_FIELD))}


def _panel_light_action(light_on: bool):
    """空调屏显：H5 clickLight 只在开机时可切，关机时拒绝，免得顺带开机。"""

    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        state = context.service_state(_AIR_SID)
        if _to_int(state.get("power")) != _AIR_POWER_ON:
            raise ValueError("空调关机时无法切换屏幕显示，请先开机 (App 同样限制)")
        frame = _air_frame(context, state, light=int(light_on))
        await context.async_send_service(_AIR_SID, frame)
        _optimistic_update(context, _AIR_SID, frame)

    return action


def _auto_state(context: DeviceContext) -> Mapping[str, Any]:
    return {"is_on": _to_flag(context.value(_AUTO_SID, _AUTO_FIELD))}


def _auto_action(auto_on: bool):
    """H5 switchPowerFn / autoDetectStatus: ``{switchPower: {on: 0|1}}``。"""

    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        payload = {_AUTO_FIELD: 1 if auto_on else 0}
        await context.async_send_service(_AUTO_SID, payload)
        _optimistic_update(context, _AUTO_SID, payload)

    return action


# --- 功率统计传感器 ----------------------------------------------------------


def _sensor_state(field: str):
    def state(context: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": _to_number(context.value(_POWER_CON_SID, field))}

    return state


# --- 实体声明 ----------------------------------------------------------------


def _switch_spec(
    key: str,
    name: str,
    state,
    on_action,
    off_action,
) -> EntitySpec:
    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=state,
        actions={"turn_on": on_action, "turn_off": off_action},
    )


def _climate_spec(context: DeviceContext) -> EntitySpec:
    return EntitySpec(
        platform="climate",
        key=_CLIMATE_KEY,
        name=_CLIMATE_NAME,
        state=_air_state,
        metadata={
            "hvac_modes": list(_AIR_MODES),
            # 该 HA 版本在添加实体阶段就读温度单位，必须在构造时给出。
            "temperature_unit": "°C",
            "min_temp": _AIR_MIN_TEMP,
            "max_temp": _AIR_MAX_TEMP,
            "target_temperature_step": _AIR_TEMP_STEP,
            "fan_modes": list(_AIR_FAN_MODES),
            "swing_modes": list(_swing_modes(context)),
        },
        actions={
            "turn_on": _air_action("turn_on"),
            "turn_off": _air_action("turn_off"),
            "set_hvac_mode": _air_action("set_hvac_mode"),
            "set_temperature": _air_action("set_temperature"),
            "set_fan_mode": _air_action("set_fan_mode"),
            "set_swing_mode": _air_action("set_swing_mode"),
        },
    )


class Product115JAdapter:
    """遥控大师空调伴侣 (115J): 按设备实际能力动态声明实体。

    没有的服务/字段就不建实体 —— 设备没上报 ``airKey.light`` 就没有屏显开关，没上报
    ``switchPower`` 就没有"自动判断开关机"开关，不产出点了没反应的僵尸实体。

    唯一例外是 ``climate.air`` (空调): 这类空调伴侣的核心能力就是 airKey，见
    ``_air_supported()`` —— 哪怕此刻 profile/上报都还没就绪也稳定建出空调，避免实体缺失，
    并靠诊断日志确认根因。
    """

    prod_id = _PROD_ID

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        has_air = _air_supported(context)
        _log_air_diagnostics(context, has_air)

        specs: list[EntitySpec] = []
        if has_air:
            specs.append(_climate_spec(context))
        if context.has_service(_LED_SID):
            specs.append(
                _switch_spec(
                    _LED_KEY,
                    _LED_NAME,
                    _led_state,
                    _led_action(True),
                    _led_action(False),
                )
            )
        if has_air and _panel_light_supported(context):
            specs.append(
                _switch_spec(
                    _LIGHT_KEY,
                    _LIGHT_NAME,
                    _panel_light_state,
                    _panel_light_action(True),
                    _panel_light_action(False),
                )
            )
        if context.has_service(_AUTO_SID):
            specs.append(
                _switch_spec(
                    _AUTO_KEY,
                    _AUTO_NAME,
                    _auto_state,
                    _auto_action(True),
                    _auto_action(False),
                )
            )
        for key, name, field, metadata in _SENSOR_SPECS:
            if not _has_field(context, _POWER_CON_SID, field):
                continue
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key=key,
                    name=name,
                    state=_sensor_state(field),
                    metadata=metadata,
                )
            )
        return tuple(specs)


ADAPTER = Product115JAdapter()
