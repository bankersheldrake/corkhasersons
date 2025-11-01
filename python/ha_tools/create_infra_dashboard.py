#!/usr/bin/env python3
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
from textwrap import dedent
import yaml

# --- Infra controls defaults (shared) ---
SSH_USER_DEFAULT = "homeassistant"
SSH_KEY_PATH_DEFAULT = "/ssl/ssh_keys/id_rsa_homeassistant"
SSH_KEY_PATH_HOST = '/var/lib/homeassistant/ssl/ssh_keys/id_rsa_homeassistant'
SSH_PORT_DEFAULT = 22

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "mqtt"
OUT_FILE = OUT_DIR / "glances.yaml"

GAUGE_MIN_PX = 20      # can shrink to here
GAUGE_MAX_PX = 100      # hard cap (matches name-card height)

# remove any default padding/margins added by wrappers
EXPANDER_TIGHT = {"padding": 0, "gap": 0, "child-padding": 0}
CARDMOD_NO_PAD = {"style": "ha-card { padding: 0; margin: 0; } :host { --ha-card-padding: 0px; }"}

BUTTON_CARD_TEMPLATES = {
    "compact_gauge_chip": {
        "show_name": True,
        "show_icon": True,
        "show_state": False,
        "aspect_ratio": "1/1",
        "size": "20px",
        "styles": {
            "card": [
                {"padding": "6px"},
                {"border-radius": "12px"},
                {"width": "44px"},
                {"height": "44px"},
                {"box-shadow": "none"},
                {"background": "transparent"},
            ],
            "icon": [
                {"color": (
                    # JS severity color from thresholds + optional invert
                    "[[["
                    "const v = Number(entity?.state);"
                    "const y = variables?.yellow ?? 70;"
                    "const r = variables?.red ?? 90;"
                    "const invert = variables?.invert ?? false;"
                    "if (isNaN(v)) return 'var(--disabled-text-color)';"
                    "const ok   = variables?.color_ok   || 'var(--success-color)';"
                    "const warn = variables?.color_warn || 'var(--warning-color)';"
                    "const err  = variables?.color_err  || 'var(--error-color)';"
                    "if (!invert) {"
                    "  if (v >= r) return err;"
                    "  if (v >= y) return warn;"
                    "  return ok;"
                    "} else {"
                    "  if (v <= r) return err;"
                    "  if (v <= y) return warn;"
                    "  return ok;"
                    "}"
                    "]]]"
                )}
            ],
            "name": [
                {"font-size": "9px"},
                {"font-weight": "700"},
                {"justify-self": "center"},
                {"margin-top": "-2px"},
            ],
        },
        # Multiline tooltip “Title\nvalue unit”
        "tooltip": (
            "[[["
            "const title = variables?.tooltip_title || (entity?.attributes?.friendly_name || 'Metric');"
            "const unit = entity?.attributes?.unit_of_measurement || variables?.default_unit || '';"
            "const raw = entity?.state; const num = Number(raw);"
            "const v = isNaN(num) ? raw : (variables?.decimals ?? 0) === 0 ? Math.round(num).toString() : num.toFixed(variables?.decimals);"
            "return `${title}\\n${v}${unit ? ' ' + unit : ''}`;"
            "]]]"
        ),
        # Tap flips compact/full
        "tap_action": {
            "action": "call-service",
            "service": "input_boolean.toggle",
            "data": {},
            "target": {"entity_id": "input_boolean.gauges_compact"},
        },
    }
}


tDefault = {
    "display_name": "{key}",
    "uptime_sensor": "sensor.{key}_uptime_seconds",
    "logo": "/local/images/infra/{key}_thumb_100X100.png",
    "title_styles": {
        "logo_card": {
            "card": [
                "background: #000000",
                "border-radius: 12px",
                "padding: 0",
                "margin: 0",
                "width: " + str(GAUGE_MAX_PX ) + "px",
                "height: " + str(GAUGE_MAX_PX ) + "px",
                "box-shadow: 0 2px 8px rgba(0,0,0,0.25)",
                "display: flex",
                "align-items: center",
                "justify-content: center",
                "overflow: hidden"
            ],
            "img_cell": [
                "justify-content: center",
                "align-items: center",
                "width: " + str(GAUGE_MAX_PX ) + "px",
                "height: " + str(GAUGE_MAX_PX ) + "px",
                "padding: 0"
            ],
            "entity_picture": [
                "width: " + str(GAUGE_MAX_PX ) + "px",
                "height: " + str(GAUGE_MAX_PX ) + "px",
                "object-fit: cover",
                "object-position: center",
                "border-radius: 12px",
                "margin: 0",
                "display: block"
            ]
        },
        "name_card": {
        "card": [
            "background: var(--ha-card-background, var(--card-background-color))",
            "border-radius: 12px",
            "padding: 10px 14px",
            "box-shadow: 0 2px 8px rgba(0,0,0,0.25)",
            "box-sizing: border-box",
            f"height: {GAUGE_MAX_PX}px",
            f"max-height: {GAUGE_MAX_PX}px",
            "overflow: hidden",
            "display: grid"
        ],
        "grid": [
            'grid-template-areas: "n" "l"',
            "grid-template-rows: auto auto",
            "row-gap: 4px"
        ],
        "name": [
            "font-weight: 700","font-size: 16px","text-align: left","align-self: end",
            "white-space: nowrap","overflow: hidden","text-overflow: ellipsis"
        ],
        "label": [
            "font-size: 13px","color: var(--secondary-text-color)","text-align: left","align-self: start",
            "white-space: nowrap","overflow: hidden","text-overflow: ellipsis"
        ]
        }
    },
    "systeminfo": [
        {"entity": "sensor.{key}_system_hostname",     "name": "Hostname"},
        {"entity": "sensor.{key}_system_linux_distro", "name": "Distribution"},
        {"entity": "sensor.{key}_system_os_name",      "name": "OS"},
        {"entity": "sensor.{key}_system_os_version",   "name": "Kernel"},
        {"entity": "sensor.{key}_system_platform",     "name": "Platform"}
    ],
    "gauges": {
        "space": {"name": "SPACE", "entity": "sensor.{key}_fs_percent",
                 "severity": {"green": 0, "yellow": 70, "red": 90}},
        "cpu":  {"name": "CPU",  "entity": "sensor.{key}_cpu_total",
                 "severity": {"green": 0, "yellow": 70, "red": 90}},
        "ram":  {"name": "RAM",  "entity": "sensor.{key}_mem_percent",
                 "severity": {"green": 0, "yellow": 70, "red": 90}}
    },
    "charts": [
        {
            "load": [{
                "min1":  {"entity": "sensor.{key}_load_min1",  "name": "CPU Load (1 min)",  "color": "#1f77b4", "stroke": 1.2},
                "min5":  {"entity": "sensor.{key}_load_min5",  "name": "CPU Load (5 min)",  "color": "#ff7f0e", "stroke": 1.5},
                "min15": {"entity": "sensor.{key}_load_min15", "name": "CPU Load (15 min)", "color": "#d62728", "stroke": 2.0},
                "cores": "sensor.{key}_load_cpucore",
                "title": "{key} Load (% of cores)"
            }],
            "network": ["eth0"] 
        }
    ],    
}

def _srv_opt(s: dict, name: str, default=None):
    v = s.get(name)
    return default if v in (None, "") else v

def _ssh_host_for(s: dict) -> str | None:
    return s.get("ip")

def _ssh_port_for(s: dict) -> int:
    # prefer per-server ssh_port; else generic 'port'; else 22
    return int(s.get("ssh_port") or SSH_PORT_DEFAULT)

def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")

def _controls_popup_tap_action(server: dict) -> dict | None:
    """
    If this server is 'control-ready', return a tap_action that opens a browser_mod popup
    with Reboot/Shutdown buttons that call the shell_command services.
    Otherwise return None (so we keep action: none).
    """
    if not server.get("enable_controls", True):
        return None

    host = _ssh_host_for(server)
    if not host:
        return None

    slug = _slug(server["key"])
    return {
        "action": "call-service",
        "service": "browser_mod.popup",
        "data": {
            "title": f"{server.get('display_name') or server['key']} controls",
            "content": {
                "type": "vertical-stack",
                "cards": [
                    {
                        "type": "button",
                        "name": "Reboot",
                        "icon": "mdi:restart",
                        "tap_action": {
                            "action": "call-service",
                            "service": f"shell_command.ssh_reboot_{slug}",
                        },
                    },
                    {
                        "type": "button",
                        "name": "Shutdown",
                        "icon": "mdi:power",
                        "tap_action": {
                            "action": "call-service",
                            "service": f"shell_command.ssh_shutdown_{slug}",
                        },
                    },
                ],
            },
        },
    }


def _load_chart(server: dict) -> dict:
    key = server["key"]
    tCustomLoad = server.get("load", {}) or {}
    tDefaultLoad = _templ(tDefault["load"], key)

    cores = tCustomLoad.get("cores", tDefaultLoad["cores"])
    title = tCustomLoad.get("title", tDefaultLoad["title"])

    def _series(cfg: dict) -> dict:
        stroke = cfg.get("stroke") or cfg.get("stroke_width", 1.2)
        return {
            "entity": cfg["entity"],
            "name": cfg["name"],
            "color": cfg["color"],
            "stroke_width": stroke,
            "transform": (
                "const v = parseFloat(entity.state); const cores = "
                f"parseFloat(hass.states['{cores}']?.state);"
                "return (isFinite(v) && isFinite(cores) && cores > 0) ? "
                "(v / cores) * 100 : null;"
            ),
        }

    tSeries = []
    for sLoadPeriod in ["min1", "min5", "min15"]:
        cfg = tCustomLoad.get(sLoadPeriod, {})
        cfg = {**tDefaultLoad[sLoadPeriod], **cfg}
        tSeries.append(_series(cfg))

    return {
        "type": "custom:apexcharts-card",
        "header": {"show": True, "title": title},
        "graph_span": "24h",
        "update_interval": "30s",
        "now": {"show": True, "label": "now"},
        "apex_config": {
            "stroke": {"width": 1.5, "curve": "straight"},
            "yaxis": [{
                "decimalsInFloat": 0,
                "title": {"text": "% of cores"},
                "labels": {
                    "formatter": "EVAL:function (v) { return (v == null || isNaN(v)) ? '-' : Math.round(v) + '%'; }"
                },
            }],
        },
        "series": tSeries,
    }


def _network_charts(server: dict):
    key = server["key"]
    n_def_map = _templ_vars(tDefault["network"], key=key)
    n_custom_map = _normalize_network_map(server)

    if server.get("network") is None:
        interfaces = sorted(n_def_map.keys())
    else:
        interfaces = sorted(n_custom_map.keys())

    if not interfaces:
        return []

    charts = []
    any_default_shape = next(iter(n_def_map.values()))

    for iface in interfaces:
        base = n_def_map.get(iface, any_default_shape)
        override = n_custom_map.get(iface, {})
        cfg = _templ_vars({**base, **override}, key=key, interface=iface)

        sent = cfg.get("sent")  or f"sensor.{key}_network_{iface}_bytes_sent_rate_per_sec"
        recv = cfg.get("recv")  or f"sensor.{key}_network_{iface}_bytes_recv_rate_per_sec"
        title = cfg.get("title") or f"{key} {iface} network"

        charts.append({
            "type": "custom:apexcharts-card",
            "header": {"show": True, "title": title},
            "graph_span": "6h",
            "update_interval": "10s",
            "now": {"show": True, "label": "now"},
            "apex_config": {
                "stroke": {"width": 1.5, "curve": "smooth"},
                "tooltip": {
                    "y": {"formatter":
                        "EVAL:function (v) { if (v == null || isNaN(v)) return '-'; return (v < 0 ? '-' : '') + Math.abs(v).toFixed(1) + ' Mbps'; }"
                    }
                },
                "yaxis": [{
                    "decimalsInFloat": 1,
                    "labels": {"formatter": "EVAL:function (v) { return v + ' Mbps'; }"},
                }],
            },
            "series": [
                {
                    "entity": sent,
                    "name": "sent",
                    "type": "line",
                    "color": "#ff7f0e",
                    "stroke_width": 1.2,
                    "opacity": 0.35,
                    "show": {"in_header": True, "legend_value": False},
                    "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;",
                },
                {
                    "entity": sent,
                    "name": "sent avg",
                    "type": "line",
                    "color": "#ff7f0e",
                    "opacity": 0.8,
                    "show": {"in_header": False, "legend_value": False},
                    "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;",
                    "group_by": {"duration": "10min", "func": "avg"},
                },
                {
                    "entity": recv,
                    "name": "recv",
                    "type": "line",
                    "color": "#1f77b4",
                    "stroke_width": 1.2,
                    "opacity": 0.35,
                    "curve": "smooth",
                    "show": {"in_header": True, "legend_value": False},
                    "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;",
                },
                {
                    "entity": recv,
                    "name": "recv avg",
                    "type": "line",
                    "color": "#1f77b4",
                    "opacity": 0.8,
                    "show": {"in_header": False, "legend_value": False},
                    "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;",
                    "group_by": {"duration": "10min", "func": "avg"},
                },
            ],
        })
    return charts


def _charts_grid(server: dict) -> dict:
    """Return a 12-col grid where each chart spans 4 cols (max 3 per row)."""
    # Existing chart builders you already have:
    load_chart = _load_chart(server)
    net_charts = _network_charts(server)  # list

    # Force each chart card to "span 4" in the nested grid
    def span4(card: dict) -> dict:
        c = deepcopy(card)
        c["view_layout"] = {"grid-column": "span 4"}
        return c

    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {
            "grid-gap": "12px",
            "grid-auto-rows": "min-content",
            "grid-template-columns": "repeat(12, 1fr)"
        },
        "cards": [span4(load_chart), *(span4(c) for c in net_charts)]
    }


# ---------- templating helpers ----------

def _templ(obj, key: str):
    if isinstance(obj, str):
        return obj.replace("{key}", key)
    if isinstance(obj, dict):
        return {k: _templ(v, key) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_templ(v, key) for v in obj]
    return obj

def _templ_vars(obj, **vars_):
    def _apply(s: str) -> str:
        for k, v in vars_.items():
            s = s.replace("{" + k + "}", str(v))
        return s
    if isinstance(obj, str):
        return _apply(obj)
    if isinstance(obj, dict):
        return {k: _templ_vars(v, **vars_) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_templ_vars(v, **vars_) for v in obj]
    return obj

def fnFallbackDefault(server: dict, psProp: str, poDefault=None):
    key = server.get("key")
    if not key:
        raise ValueError("server['key'] is required")
    if psProp in server and server[psProp] is not None:
        return _templ(server[psProp], key)
    if psProp in tDefault and tDefault[psProp] is not None:
        return _templ(deepcopy(tDefault[psProp]), key)
    return _templ(deepcopy(poDefault), key) if poDefault is not None else None

# ---------- card builders ----------
def _swap_chart(server: dict) -> dict:
    key = server["key"]
    ent_pct  = f"sensor.{key}_memswap_percent"
    ent_used = f"sensor.{key}_memswap_used"  # published by your MQTT generator

    return {
        "type": "custom:apexcharts-card",
        "header": {"show": True, "title": f"{key} Swap"},
        "graph_span": "24h",
        "update_interval": "30s",
        "now": {"show": True, "label": "now"},
        "apex_config": {
            "stroke": {"width": 1.6, "curve": "straight"},
            "yaxis": [
                {"title": {"text": "%"}, "min": 0, "max": 100,
                 "labels": {"formatter": "EVAL:(v)=> (v==null||isNaN(v))?'-':Math.round(v)+'%'"}
                },
                {"opposite": True, "title": {"text": "GB"},
                 "labels": {"formatter": "EVAL:(v)=> (v==null||isNaN(v))?'-':v.toFixed(1)+' GB'"}
                }
            ]
        },
        "series": [
            {"entity": ent_pct,  "name": "Swap %",  "type": "line", "color": "#2ca02c",
             "stroke_width": 1.6, "yaxis_id": 0,
             "transform": "const v=parseFloat(entity.state); return Number.isFinite(v)?v:null;"},
            {"entity": ent_used, "name": "Used (GB)", "type": "line", "color": "#17becf",
             "stroke_width": 1.2, "opacity": 0.8, "yaxis_id": 1,
             "transform": "const v=parseFloat(entity.state); return Number.isFinite(v)?v:null;"}
        ]
    }

def _offline_placeholder_card(server: dict) -> dict:
    """
    A single card, visually similar in height to the gauges row,
    centered 'OFFLINE' label.
    """
    return {
        "type": "custom:button-card",
        "name": "OFFLINE",
        "show_icon": False,
        "tap_action": {"action": "none"},
        "styles": {
            "card": [
                {"background": "var(--ha-card-background, var(--card-background-color))"},
                {"border-radius": "12px"},
                {"box-shadow": "0 2px 8px rgba(0,0,0,0.25)"},
                {"display": "flex"},
                {"align-items": "center"},
                {"justify-content": "center"},
                # keep roughly same vertical footprint as your gauges
                {"height": f"{GAUGE_MAX_PX}px"},
                {"max-height": f"{GAUGE_MAX_PX}px"},
                {"min-height": f"{GAUGE_MIN_PX}px"},
                {"padding": "0"},
            ],
            "name": [
                {"font-weight": "900"},
                {"letter-spacing": ".12em"},
                {"text-transform": "uppercase"},
                {"font-size": "clamp(24px, 5vw, 48px)"},
                {"color": "var(--error-color, rgba(220,38,38,0.9))"},
                {"text-shadow": "0 2px 8px rgba(0,0,0,.25)"},
            ]
        }
    }

def _button_card_styles(style_section: list[str]) -> list[dict]:
    """
    Convert a list of CSS strings into list-of-dicts format required by button-card 'styles'.
    E.g. ["padding: 4px", "height: 84px"] -> [{"padding":"4px"},{"height":"84px"}]
    """
    out = []
    for line in style_section:
        if ":" in line:
            k, v = line.split(":", 1)
            out.append({k.strip(): v.strip()})
    return out

def _title_name_buttoncard(server: dict) -> dict:
    key = server["key"]
    title = fnFallbackDefault(server, "display_name", key)
    uptime_sensor = fnFallbackDefault(server, "uptime_sensor")
    ping = fnFallbackDefault(server, "ping", key)
    name_styles = fnFallbackDefault(server, "title_styles")["name_card"]
    return {
        "type": "custom:button-card",
        "name": title,
        "show_icon": False,
        "show_label": True,
        "tap_action": {"action": "none"},
        "styles": {
            "card": _button_card_styles(name_styles.get("card", [])),
            "grid": _button_card_styles(name_styles.get("grid", [])),
            "name": _button_card_styles(name_styles.get("name", [])),
            "label": _button_card_styles(name_styles.get("label", [])),
        },
        "label": _status_label_js(key, ping, uptime_sensor),
    }


# def _gauge_card(entity: dict) -> dict:
#     return {
#         "type": "gauge",
#         "name": entity["name"],
#         "entity": entity["entity"],
#         "min": 0,
#         "max": 100,
#         "severity": deepcopy(entity["severity"]),
#     }


def _gauge_card(cfg: dict) -> dict:
    """Native HA gauge kept square with card-mod; responsive clamp sizing."""
    card = {
        "type": "gauge",
        "entity": cfg["entity"],
        "name": cfg.get("name", ""),
        "min": cfg.get("min", 0),
        "max": cfg.get("max", 100),
        "needle": False,  # or True if you prefer
        "severity": {
            # HA expects thresholds that switch color at these values
            "green": cfg["severity"]["green"],
            "yellow": cfg["severity"]["yellow"],
            "red": cfg["severity"]["red"],
        },
        # Keep the gauge square and capped in size (requires card-mod)
        "card_mod": {
            "style": f"""
              ha-card {{
                aspect-ratio: 1 / 1;
                width: clamp({GAUGE_MIN_PX}px, 12vw, {GAUGE_MAX_PX}px);
                max-width: {GAUGE_MAX_PX}px;
                max-height: {GAUGE_MAX_PX}px;
                min-width: {GAUGE_MIN_PX}px;
                min-height: {GAUGE_MIN_PX}px;
              }}
            """
        }
    }
    return card

def _resolve_speed_cfg(server: dict) -> dict | None:
    """
    Supports either top-level 'speed' or 'gauges.speed' in server config.
    Truthy bool => use defaults. Dict => allow overrides.
    """
    key = server["key"]
    raw = server.get("speed")
    if raw is None:
        g = server.get("gauges") or {}
        raw = g.get("speed")

    if not raw:
        return None

    cfg = {
        "name": "SPEED",
        "min": 0, "max": 250, "cardwidth": GAUGE_MAX_PX,
        "download": {
            "entity": f"sensor.{key}_speedtest_download",
            "label": "",
            "severity": {"green": 100, "yellow": 50, "red": 0}
        },
        "upload": {
            "entity": f"sensor.{key}_speedtest_upload",
            "label": "",
            "severity": {"green": 40, "yellow": 15, "red": 0}
        },
        "graph_span": "24h",
        "bucket": "5min"
    }

    if isinstance(raw, dict):
        # top-level overrides (name/min/max/graph_span/bucket)
        for k in ("name", "min", "max", "graph_span", "bucket"):
            if k in raw: cfg[k] = raw[k]
        if isinstance(raw.get("download"), dict):
            cfg["download"].update(raw["download"])
        if isinstance(raw.get("upload"), dict):
            cfg["upload"].update(raw["upload"])

    return cfg


def _label_button(name: str, tap_popup: dict | None = None) -> dict:
    """A tiny button-card label row under a gauge."""
    card = {
        "type": "custom:button-card",
        "name": name,   # ← preserve gauge's own label
        "show_icon": False,
        "show_state": False,
        "styles": {
            "card": [
                "padding: 0",
                "margin: 0",
                "height: 22px",
                "border-radius: 0",
                "background: transparent",
                "box-shadow: none"
            ],
            "name": [
                "font-weight: 700",
                "font-size: 12px",
                "letter-spacing: 0.06em",
                "color: var(--primary-text-color)",
                "justify-self: center"
            ]
        },
        "tap_action": {"action": "none"}
    }
    if tap_popup:
        card["tap_action"] = {
            "action": "call-service",
            "service": "browser_mod.popup",
            "data": tap_popup
        }
    return card

def _gauge_card_no_label(cfg: dict) -> dict:
    """Gauge with no caption (force empty name to avoid friendly name fallback)."""
    card = {
        "type": "gauge",
        "entity": cfg["entity"],
        "name": "", 
        "min": cfg.get("min", 0),
        "max": cfg.get("max", 100),
        "needle": cfg.get("needle", False),
    }
    if "severity" in cfg:
        card["severity"] = cfg["severity"]
    return card


def _square_stack(gauge_card: dict, label_card: dict) -> dict:
    """Wrap [gauge, label] in a fixed square tile (no gaps between rows)."""
    return {
        "type": "custom:mod-card",
        "style": f"""
          ha-card {{
            aspect-ratio: 1 / 1;
            width: clamp({GAUGE_MIN_PX}px, 12vw, {GAUGE_MAX_PX}px);
            max-width: {GAUGE_MAX_PX}px;
            max-height: {GAUGE_MAX_PX}px;
            min-width: {GAUGE_MIN_PX}px;
            min-height: {GAUGE_MIN_PX}px;
            padding: 0 !important;
            margin: 0 !important;
            overflow: hidden;
          }}
        """,
        "card": {
            "type": "custom:vertical-stack-in-card",
            "cards": [
                {
                    "type": "custom:mod-card",
                    "style": (
                        "ha-card { "
                        "padding: 0 !important; "
                        "margin: 0 !important; "
                        "height: calc(100% - 22px); "
                        "box-shadow: none; }"
                    ),
                    "card": gauge_card
                },
                {
                    **label_card,
                    "card_mod": {
                        "style": (
                            "ha-card { "
                            "padding: 0 !important; "
                            "margin: 0 !important; "
                            "box-shadow: none; }"
                        )
                    }
                }
            ]
        }
    }

def _dual_speed_stack_card(cfg: dict) -> dict:
    """Dual download/upload gauge on top, clickable SPEED label below."""
    name = cfg.get("name", "SPEED")
    d = cfg["download"]["entity"]
    u = cfg["upload"]["entity"]
    graph_span = cfg.get("graph_span", "24h")
    bucket = cfg.get("bucket", "5min")

    dual = {
        "type": "custom:dual-gauge-card",
        "min": cfg.get("min", 0),
        "max": cfg.get("max", 250),
        "cardwidth": GAUGE_MAX_PX,
        "outer": {
            "entity": d,
            "label": "",
            "unit": "Mbps",
            "colors": cfg["download"].get(
                "colors",
                [
                    {"value": 100, "color": "var(--label-badge-green)"},
                    {"value": 50, "color": "var(--label-badge-yellow)"},
                    {"value": 0, "color": "var(--label-badge-red)"}
                ],
            ),
        },
        "inner": {
            "entity": u,
            "label": "",
            "unit": "Mbps",
            "colors": cfg["upload"].get(
                "colors",
                [
                    {"value": 40, "color": "var(--label-badge-green)"},
                    {"value": 15, "color": "var(--label-badge-yellow)"},
                    {"value": 0, "color": "var(--label-badge-red)"}
                ],
            ),
        },
        "card_mod": {
            "style": """
              ha-card { padding: 0 !important; margin: 0 !important; }
              .card-header, .header { display: none !important; }
              .card-content { padding: 0 !important; margin: 0 !important; line-height: 0; }
              .dual-gauge-card, .dual-gauge__container, .dual-gauge__svg, svg {
                width: 100% !important;
                height: 100% !important;
                display: block;
              }
              text { font-size: 0.8em !important; }
            """
        }
    }

    # fdsa = {
    #     "type": "custom:apexcharts-card",
    #     "header": {"show": True, "title": title},
    #     "graph_span": "6h",
    #     "update_interval": "10s",
    #     "now": {"show": True, "label": "now"},
    #     "apex_config": {
    #         "stroke": {"width": 1.5, "curve": "smooth"},
    #         "tooltip": {"y": {"formatter":
    #             "EVAL:function (v) { if (v == null || isNaN(v)) return '-'; return (v < 0 ? '-' : '') + Math.abs(v).toFixed(1) + ' Mbps'; }"}},
    #         "yaxis": [{"decimalsInFloat": 1, "labels": {"formatter": "EVAL:function (v) { return v + ' Mbps'; }"}}],
    #     },
    #     "series": [
    #         {"entity": sent_ent, "name": "sent", "type": "line", "color": "#ff7f0e", "stroke_width": 1.2,
    #          "opacity": 0.35, "show": {"in_header": True, "legend_value": False},
    #          "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;"},
    #         {"entity": sent_ent, "name": "sent avg", "type": "line", "color": "#ff7f0e", "opacity": 0.8,
    #          "show": {"in_header": False, "legend_value": False},
    #          "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;",
    #          "group_by": {"duration": "10min", "func": "avg"}},
    #         {"entity": recv_ent, "name": "recv", "type": "line", "color": "#1f77b4", "stroke_width": 1.2,
    #          "opacity": 0.35, "curve": "smooth", "show": {"in_header": True, "legend_value": False},
    #          "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;"},
    #         {"entity": recv_ent, "name": "recv avg", "type": "line", "color": "#1f77b4", "opacity": 0.8,
    #          "show": {"in_header": False, "legend_value": False},
    #          "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;",
    #          "group_by": {"duration": "10min", "func": "avg"}},
    #     ],
    # }
    popup = {
        "title": f"{name} history",
        "content": {
            "type": "custom:apexcharts-card",
            "header": {
                "show": True,
                "title": f"{name} ({graph_span})",
                "show_states": True,
                "colorize_states": True
            },
            "graph_span": graph_span,
            "update_interval": "60s",
            # "now": True,
            "now": {"show": True, "label": "now"},
            "apex_config": {
                "yaxis": [
                    {"id": "down", "decimalsInFloat": 1,                "labels": {"formatter": "EVAL:function (v) { if (v==null || isNaN(v)) return '-'; return Math.round(v) + ' Mbps'; }" }},
                    {"id": "up", "decimalsInFloat": 1,"opposite": True, "labels": {"formatter": "EVAL:function (v) { if (v==null || isNaN(v)) return '-'; return Math.round(v) + ' Mbps'; }" }}
                ],
                "tooltip": {"y": {"formatter": "EVAL:function (v) { return (v==null?'':v.toFixed(1)+' Mbps'); }"}}
            },
            "series": [
                {"entity": d, "name": "Download", "yaxis_id": "down", "type": "line"
                    , "group_by": {"func": "avg", "duration": bucket}
                    , "stroke_width": 2
                    , "show": {"in_header": False, "legend_value": False}
                },
                {"entity": u, "name": "Upload", "yaxis_id": "up", "type": "line"
                    , "group_by": {"func": "avg", "duration": bucket}
                    , "stroke_width": 2
                    , "show": {"in_header": False, "legend_value": False}
                 }
            ]
        }
    }

    return _square_stack(dual, _label_button(name, tap_popup=popup))

    
def _single_gauge_stack(cfg: dict) -> dict:
    """Gauge without inline label, plus external label card."""
    label_text = cfg.get("name", "")
    gauge = _gauge_card_no_label(cfg)
    label = _label_button(label_text)
    return _square_stack(gauge, label)



def _cpu_chart_from_cfg(server: dict, load_cfg: dict) -> dict:
    key = server["key"]
    cfg = _templ(load_cfg, key)
    def_defaults = {
        "min1":  {"entity": f"sensor.{key}_load_min1",  "name": "CPU Load (1 min)",  "color": "#1f77b4", "stroke": 1.2},
        "min5":  {"entity": f"sensor.{key}_load_min5",  "name": "CPU Load (5 min)",  "color": "#ff7f0e", "stroke": 1.5},
        "min15": {"entity": f"sensor.{key}_load_min15", "name": "CPU Load (15 min)", "color": "#d62728", "stroke": 2.0},
    }
    title = cfg.get("title", f"{key} Load")
    cores_ent = cfg.get("cores")
    series = []
    for k in ["min1","min5","min15"]:
        base = deepcopy(def_defaults.get(k, {}))
        base.update(cfg.get(k, {}))
        ent = base.get("entity")
        if not ent: continue
        s = {
            "entity": ent,
            "name": base.get("name", k),
            "color": base.get("color", "#1f77b4"),
            "stroke_width": base.get("stroke", 1.2),
        }
        if cores_ent:
            s["transform"] = (
                "const v = parseFloat(entity.state); "
                f"const cores = parseFloat(hass.states['{cores_ent}']?.state); "
                "return (isFinite(v) && isFinite(cores) && cores > 0) ? (v / cores) * 100 : null;"
            )
        else:
            s["transform"] = "const v = parseFloat(entity.state); return Number.isFinite(v) ? v : null;"
        series.append(s)
    yaxis = [{
        "decimalsInFloat": 0 if cores_ent else 2,
        "title": {"text": "% of cores" if cores_ent else "Load"},
        "labels": {"formatter": "EVAL:function (v) { "
                    "if (v == null || isNaN(v)) return '-'; "
                    "return " + ("'Math.round(v)+\"%\"'" if cores_ent else " 'v.toFixed(2)'" ) + "; }"},
    }]
    return {
        "type": "custom:apexcharts-card",
        "header": {"show": True, "title": title},
        "graph_span": "24h",
        "update_interval": "30s",
        "now": {"show": True, "label": "now"},
        "apex_config": {"stroke": {"width": 1.5, "curve": "straight"}, "yaxis": yaxis},
        "series": series,
    }

def _network_chart_for(key: str, iface: str, sent_ent: str, recv_ent: str, title: str) -> dict:
    return {
        "type": "custom:apexcharts-card",
        "header": {"show": True, "title": title},
        "graph_span": "6h",
        "update_interval": "10s",
        "now": {"show": True, "label": "now"},
        "apex_config": {
            "stroke": {"width": 1.5, "curve": "smooth"},
            "tooltip": {"y": {"formatter":
                "EVAL:function (v) { if (v == null || isNaN(v)) return '-'; return (v < 0 ? '-' : '') + Math.abs(v).toFixed(1) + ' Mbps'; }"}},
            "yaxis": [{"decimalsInFloat": 1, "labels": {"formatter": "EVAL:function (v) { return v + ' Mbps'; }"}}],
        },
        "series": [
            {"entity": sent_ent, "name": "sent", "type": "line", "color": "#ff7f0e", "stroke_width": 1.2,
             "opacity": 0.35, "show": {"in_header": True, "legend_value": False},
             "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;"},
            {"entity": sent_ent, "name": "sent avg", "type": "line", "color": "#ff7f0e", "opacity": 0.8,
             "show": {"in_header": False, "legend_value": False},
             "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? - (v * 8) / 1e6 : null;",
             "group_by": {"duration": "10min", "func": "avg"}},
            {"entity": recv_ent, "name": "recv", "type": "line", "color": "#1f77b4", "stroke_width": 1.2,
             "opacity": 0.35, "curve": "smooth", "show": {"in_header": True, "legend_value": False},
             "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;"},
            {"entity": recv_ent, "name": "recv avg", "type": "line", "color": "#1f77b4", "opacity": 0.8,
             "show": {"in_header": False, "legend_value": False},
             "transform": "const v = parseFloat(entity.state); return Number.isFinite(v) ? (v * 8) / 1e6 : null;",
             "group_by": {"duration": "10min", "func": "avg"}},
        ],
    }

def _swap_chart_for(sensor_entity: str, title: str) -> dict:
    return {
        "type": "custom:apexcharts-card",
        "header": {"show": True, "title": title},
        "graph_span": "24h",
        "update_interval": "30s",
        "now": {"show": True, "label": "now"},
        "apex_config": {
            "stroke": {"width": 1.5, "curve": "straight"},
            "yaxis": [{"decimalsInFloat": 0, "title": {"text": "%"},
                       "labels": {"formatter": "EVAL:function (v) { return (v == null || isNaN(v)) ? '-' : Math.round(v) + '%'; }"}}],
        },
        "series": [{"entity": sensor_entity, "name": "Swap %", "type": "line", "color": "#9467bd", "stroke_width": 1.6}],
    }

def _charts_grid_from_cards(cards: list[dict]) -> dict:
    def span4(c: dict) -> dict:
        cc = deepcopy(c); cc["view_layout"] = {"grid-column": "span 4"}; return cc
    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {"grid-gap": "12px", "grid-auto-rows": "min-content", "grid-template-columns": "repeat(12, 1fr)"},
        "cards": [span4(c) for c in cards]
    }


def _wol_host_for(s: dict) -> str | None:
    """
    Resolve the host to use for WoL switch state checking.
    Priority: explicit 'wol_host' → generic 'host' → 'ip'.
    Returns None if none are set.
    """
    return s.get("wol_host") or s.get("ip")

def gather_prereq_findings(config: dict) -> dict:
    findings = {"global": {}, "servers": {}}
    ssh_bin_missing = shutil.which("ssh") is None
    findings["global"]["ssh_bin_missing"] = ssh_bin_missing

    key_path = Path(config.get("ssh_key_path", SSH_KEY_PATH_DEFAULT))
    findings["global"]["ssh_key_path"] = str(key_path)
    findings["global"]["ssh_key_missing"] = not Path(SSH_KEY_PATH_HOST).exists()

    for s in config.get("servers", []):
        key = s.get("key")
        if not key:
            continue

        controls = bool(s.get("enable_controls", True))
        ssh_host = _ssh_host_for(s)
        wol_host = _wol_host_for(s)
        mac = s.get("mac")

        per_srv_key_path = Path(s.get("ssh_key_path") or key_path)
        notes = []
        if controls:
            if not ssh_host:
                notes.append("No SSH host provided (`ssh_host`, `host`, or `ip`). SSH controls will be skipped.")
            wol_enabled = s.get("wol", bool(s.get("mac") or s.get("wol_host")))
            if wol_enabled and not mac:
                notes.append("No MAC provided → WoL switch will be skipped.")
            if not Path(SSH_KEY_PATH_HOST).exists():
                notes.append(f"SSH private key not found at {per_srv_key_path}.")

        findings["servers"][key] = {
            "controls_enabled": controls,
            "ssh_host": ssh_host,  
            "wol_host": wol_host,
            "mac_missing": not bool(mac),
            "notes": notes,
            "ssh_key_path": str(per_srv_key_path),
            "ssh_user": s.get("ssh_user") or SSH_USER_DEFAULT,
            "ssh_port": _ssh_port_for(s),
        }
    return findings


def render_instructions(findings: dict) -> str:
    """
    Produce a human-friendly report with next steps, including copy/paste commands.
    """
    g = findings["global"]
    lines = []

    lines.append("Infrastructure Controls – Post-run Checklist\n")
    lines.append("=================================================\n")

    if g.get("ssh_bin_missing", False):
        lines.append("• `ssh` binary not found on this machine. Install OpenSSH client.\n")

    key_path_in_container = g.get("ssh_key_path", SSH_KEY_PATH_DEFAULT)

    if g.get("ssh_key_missing"):
        lines.append(f"• SSH private key expected at (inside HA container): {key_path_in_container}  (not found)\n")
        lines.append(f"  Host-side path: {SSH_KEY_PATH_DEFAULT}\n")
        lines.append(dedent(f"""\
            Create it on the HOST:
              sudo mkdir -p {SSH_KEY_PATH_DEFAULT.rsplit('/',1)[0]}
              sudo ssh-keygen -t rsa -f {SSH_KEY_PATH_DEFAULT} -N ""
            # This creates:
            #   private key: {key_path_in_container}
            #   public key : {key_path_in_container}.pub
        """))
    else:
        lines.append(f"• SSH key present (inside HA): {key_path_in_container}\n")

    lines.append("\nPer-server notes\n---------------------------------------------\n")
    for key, s in findings["servers"].items():
        lines.append(f"[{key}]")
        if not s["controls_enabled"]:
            lines.append("  - Controls are disabled (enable_controls=false).")
            lines.append("")
            continue

        ssh_host = s.get("ssh_host")
        ssh_port = s.get("ssh_port")
        user     = s.get("ssh_user")
        kpth     = s.get("ssh_key_path")

        # Only include ssh-copy-id instructions if we actually have a host/IP
        if ssh_host:
            lines.append("  - Authorize key & test (using the correct port):")
            lines.append(dedent(f"""\
                # (on the remote host, one-time)
                sudo adduser {user}
                sudo visudo
                # add this line:
                {user} ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/reboot, /sbin/shutdown

                # (from the HA host) copy the key to the REAL host (no placeholders)
                sudo ssh-copy-id -i {SSH_KEY_PATH_HOST}.pub -p {ssh_port} {user}@{ssh_host}

                # test key-only auth from HOST
                sudo ssh -i {SSH_KEY_PATH_HOST} -p {ssh_port} {user}@{ssh_host} "echo ok"
            """).rstrip())
        else:
            # No host → don't print ssh-copy-id/test block at all
            lines.append("  - No SSH host provided → skipping ssh-copy-id/test instructions.")

        # Any extra notes (missing MAC, missing key path, etc.)
        for n in s.get("notes", []):
            lines.append(f"  - {n}")

        lines.append("")  # spacing


    lines.append("Tips:\n")
    lines.append("• Ensure Wake-on-LAN is enabled in BIOS/NIC settings for each host.\n")
    lines.append("• After fixing items above, restart Home Assistant.\n")

    return "\n".join(lines)


def write_instructions(findings: dict, output_cfg: dict):
    """
    Write a text file with the instructions and also echo a short summary in stdout.
    """
    default_path = "ha_fragments/infra_controls_README.txt"
    out_path = Path(output_cfg.get("controls_readme_file", default_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = render_instructions(findings)
    out_path.write_text(doc, encoding="utf-8")

    # Short console summary
    print(f"📄 Wrote post-run checklist: {out_path}")
    any_gaps = (
        findings["global"].get("ssh_bin_missing")
        or findings["global"].get("ssh_key_missing")
        or any(
            v["ip_missing"] or v["mac_missing"] or ("SSH private key not found" in " ".join(v["notes"]))
            for v in findings["servers"].values()
            if v.get("controls_enabled", True)
        )
    )
    if any_gaps:
        print("⚠️  One or more prerequisites are missing. See the checklist for exact steps.")
    else:
        print("✅ All expected prerequisites appear present.")

def write_shell_command_files(config: dict, findings: dict, out_dir: Path | None = None) -> None:
    """
    Creates one file per 'ready' server under a directory intended for:
      shell_command: !include_dir_merge_list shell_commands/

    Each file is a YAML list (because you're using !include_dir_merge_list).
    A server is 'ready' if:
      - controls_enabled is True
      - ssh_host is present
      - the chosen private key file exists (global or per-server override)
    """
    # default output dir next to configuration.yaml, adjust if you prefer
    if out_dir is None:
        out_dir = Path(config.get("output", {}).get("shell_commands_dir",
                        "/var/lib/homeassistant/homeassistant/shell_commands"))
    out_dir.mkdir(parents=True, exist_ok=True)

    global_key_path = Path(findings["global"].get("ssh_key_path", SSH_KEY_PATH_DEFAULT))
    global_key_exists = not findings["global"].get("ssh_key_missing", False)

    created, skipped = [], []

    for s in config.get("servers", []):
        key = s.get("key")
        if not key:
            continue

        f = findings["servers"].get(key, {})
        if not f or not f.get("controls_enabled", True):
            skipped.append((key, "controls disabled"))
            continue

        ssh_host = f.get("ssh_host")
        if not ssh_host:
            skipped.append((key, "no ssh_host/host/ip"))
            continue

        # resolve per-server key path or fall back to global
        per_srv_key_path = Path(SSH_KEY_PATH_HOST)
        if not per_srv_key_path.exists():
            skipped.append((key, f"key not found at {per_srv_key_path}"))
            continue

        ssh_user = s.get("ssh_user") or SSH_USER_DEFAULT
        ssh_port = _ssh_port_for(s)

        def _key_path_in_container(p: Path | str) -> str:
            p = str(p)
            if p.startswith("/var/lib/homeassistant/ssl/"):
                return p.replace("/var/lib/homeassistant/ssl", "/ssl", 1)
            return p  # already /ssl or a custom mount

        in_container_key = _key_path_in_container(per_srv_key_path)

        base = (
            f"ssh -i {in_container_key} -p {ssh_port} "
            f"-o 'StrictHostKeyChecking=no' {ssh_user}@{ssh_host}"
        )

        shutdown_cmd = f"{base} sudo /sbin/poweroff"
        reboot_cmd   = f"{base} sudo /sbin/reboot"

        slug = _slug(key)
        file_path = out_dir / f"{slug}.yaml"

        # IMPORTANT: use folded scalars (">-") so the whole command is one string
        file_text = (
            f"ssh_shutdown_{slug}: >-\n"
            f"    {shutdown_cmd}\n\n"
            f"ssh_reboot_{slug}: >-\n"
            f"    {reboot_cmd}\n"
        )
        file_path.write_text(file_text, encoding="utf-8")
        created.append(str(file_path))

    # Console summary
    if created:
        print("✅ shell_command files created:")
        for p in created:
            print(f"  - {p}")
    else:
        print("ℹ️  No shell_command files created (no ready servers).")

    if skipped:
        print("↩️  Skipped servers:")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")


def _has_swap_gauge(server: dict) -> bool:
    g = (server.get("gauges") or {})
    for cfg in g.values():
        ent = (cfg or {}).get("entity", "")
        if "memswap_percent" in ent:
            return True
    return False

def build_shell_commands(config: dict) -> dict | None:
    cmds = {}
    for s in config.get("servers", []):
        key = s.get("key")
        if not key or not (s.get("enable_controls", True)):
            continue

        host = _ssh_host_for(s)
        if not host:
            # no SSH host → skip commands for this server
            continue

        user = s.get("ssh_user") or SSH_USER_DEFAULT
        kpth = s.get("ssh_key_path") or config.get("ssh_key_path") or SSH_KEY_PATH_DEFAULT
        port = _ssh_port_for(s)

        skey = key.lower().replace(" ", "_").replace("-", "_")
        base = f"ssh -i {kpth} -p {port} -o 'StrictHostKeyChecking=no' {user}@{host}"

        cmds[f"ssh_shutdown_{skey}"] = f"{base} sudo /sbin/poweroff"
        cmds[f"ssh_reboot_{skey}"]   = f"{base} sudo /sbin/reboot"

    return {"shell_command": cmds} if cmds else None
def _view_toggle_button() -> dict:
    return {
        "type": "custom:button-card",
        "entity": "input_boolean.gauges_compact",
        "name": "View",
        "icon": (
            "[[[ return states['input_boolean.gauges_compact']?.state === 'on' "
            "? 'mdi:view-grid-outline' : 'mdi:gauge' ]]]"
        ),
        "tap_action": {"action": "call-service", "service": "input_boolean.toggle",
                       "target": {"entity_id": "input_boolean.gauges_compact"}},
        "styles": {"card": [{"padding": "6px"}, {"border-radius": "10px"}, {"box-shadow": "none"}]},
    }

def _compact_chip_from_gauge(cfg: dict, *, icon: str, tooltip_title: str, default_unit: str = "", decimals: int = 0, invert: bool = False) -> dict:
    # cfg contains: name, entity, severity = {green,yellow,red}
    sev = cfg.get("severity", {}) or {}
    yellow = sev.get("yellow", 70); red = sev.get("red", 90)
    return {
        "type": "custom:button-card",
        "template": "compact_gauge_chip",
        "entity": cfg["entity"],
        "name": cfg.get("name", ""),
        "icon": icon,
        "variables": {
            "tooltip_title": tooltip_title,
            "yellow": yellow,
            "red": red,
            "default_unit": default_unit,
            "decimals": decimals,
            "invert": invert,
        },
    }

def _compact_grid_for_server(server: dict) -> dict:
    key = server["key"]
    # Start with your default + custom gauges (same merge logic you already do)
    default_gauges = _templ(tDefault["gauges"], key)
    custom_gauges  = server.get("gauges", {}) or {}
    merged_keys = list(dict.fromkeys([*default_gauges.keys(), *custom_gauges.keys()]))

    chips = []
    for gid in merged_keys:
        cfg = {**default_gauges.get(gid, {}), **custom_gauges.get(gid, {})}
        ent = cfg.get("entity")
        if not ent:
            continue

        name = (cfg.get("name") or "").upper()

        # Map names → icon + tooltip; tweak units/decimals as needed
        if name == "SPACE":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:harddisk", tooltip_title="Disk Usage", default_unit="%", decimals=0))
        elif name == "CPU":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:cpu-64-bit", tooltip_title="CPU Usage", default_unit="%", decimals=0))
        elif name == "RAM":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:memory", tooltip_title="RAM Usage", default_unit="%", decimals=0))
        elif name == "TEMP":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:thermometer", tooltip_title="CPU Temperature", default_unit="°C", decimals=0))
        elif name == "SWAP":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:swap-horizontal", tooltip_title="Swap Usage", default_unit="%", decimals=0))
        elif name == "DISK":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:chart-bell-curve", tooltip_title="Disk Throughput", default_unit="MB/s", decimals=0))
        elif name == "IOPS":
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:swap-vertical", tooltip_title="Disk IOPS", default_unit="", decimals=0))
        else:
            # Default icon + title fallback
            chips.append(_compact_chip_from_gauge(cfg, icon="mdi:circle", tooltip_title=name or "Metric"))

    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {
            "grid-gap": "8px",
            "padding": "0",
            "grid-template-columns": "repeat(auto-fit, minmax(20px, 52px))"
        },
        "cards": chips,
        "card_mod": CARDMOD_NO_PAD
    }


def _build_chart_cards(server: dict, has_swap: bool) -> list[dict]:
    key = server["key"]
    cards = []
    charts_spec = server.get("charts", None)
    if charts_spec is None:
        charts_spec = _templ(tDefault["charts"], key)
    if isinstance(charts_spec, dict):
        charts_spec = [charts_spec]
    if not isinstance(charts_spec, list):
        return cards

    for block in charts_spec:
        if not isinstance(block, dict): continue

        # LOAD
        load_part = block.get("load")
        if isinstance(load_part, dict):
            cards.append(_cpu_chart_from_cfg(server, load_part))
        elif isinstance(load_part, list):
            for lc in load_part:
                if isinstance(lc, dict):
                    cards.append(_cpu_chart_from_cfg(server, lc))

        # NETWORK
        net_list = block.get("network", [])
        if isinstance(net_list, list):
            for item in net_list:
                if isinstance(item, str):
                    iface = item
                    sent = f"sensor.{key}_network_{iface}_bytes_sent_rate_per_sec"
                    recv = f"sensor.{key}_network_{iface}_bytes_recv_rate_per_sec"
                    title = f"{key} {iface} network"
                    cards.append(_network_chart_for(key, iface, sent, recv, title))
                elif isinstance(item, dict) and item:
                    iface, overrides = next(iter(item.items()))
                    overrides = overrides or {}
                    sent = overrides.get("sent") or f"sensor.{key}_network_{iface}_bytes_sent_rate_per_sec"
                    recv = overrides.get("recv") or f"sensor.{key}_network_{iface}_bytes_recv_rate_per_sec"
                    title = overrides.get("title") or f"{key} {iface} network"
                    cards.append(_network_chart_for(key, iface,
                                                    _templ_vars(sent, key=key, interface=iface),
                                                    _templ_vars(recv, key=key, interface=iface),
                                                    _templ_vars(title, key=key, interface=iface)))

        # SWAP (only if requested and a swap gauge exists, OR explicit sensor string)
        swap_spec = block.get("swap", None)
        if isinstance(swap_spec, str) and swap_spec:
            cards.append(_swap_chart_for(swap_spec, f"{key} Swap %"))
        elif swap_spec is True and has_swap:
            cards.append(_swap_chart_for(f"sensor.{key}_memswap_percent", f"{key} Swap %"))

    return cards


def _normalize_network_map(server: dict) -> dict:
    raw = server.get("network")
    if not raw:
        return {}
    if isinstance(raw, list):
        return {iface: {} for iface in raw if isinstance(iface, str) and iface.strip()}
    if isinstance(raw, dict) and all(isinstance(v, dict) for v in raw.values()):
        return raw
    raise ValueError(
        f"Invalid network config for server '{server.get('key')}': expected list of interface names "
        f"or dict of interface->config, got: {type(raw).__name__}"
    )

def _system_info_card(server: dict) -> dict:
    key = server["key"]
    display_name = fnFallbackDefault(server, "display_name", key)
    default_entities = _templ(tDefault["systeminfo"], key)
    custom_entities = server.get("systeminfo")
    entities = custom_entities if custom_entities else default_entities
    return {"type": "entities", "title": f"{display_name} System Info", "entities": entities}

def server_to_grid_pair(server: dict) -> list[dict]:
    key = server["key"]
    display_name = fnFallbackDefault(server, "display_name", key)
    ping = fnFallbackDefault(server, "ping", key)

    logo = _logo_card(server); logo["view_layout"] = {"grid-column": "1"}

    expander_system = {
        "type": "custom:expander-card",
        "title-card-button-overlay": True,
        "title-card-clickable": True,
        **EXPANDER_TIGHT,
        "title-card": _title_name_buttoncard(server),
        "cards": [_system_info_card(server)],
        "view_layout": {"grid-column": "2"}
    }

    # --- NEW: a tiny compact/full toggle button (column 2)
    view_toggle = _view_toggle_button()
    view_toggle["view_layout"] = {"grid-column": "2"}

    # Build your existing FULL gauges grid
    default_gauges = _templ(tDefault["gauges"], key)
    custom_gauges = server.get("gauges", {}) or {}
    merged_keys = list(dict.fromkeys([*default_gauges.keys(), *custom_gauges.keys()]))
    gauge_cards = []
    for gid in merged_keys:
        cfg = {**default_gauges.get(gid, {}), **custom_gauges.get(gid, {})}
        if gid == "speed":   # handled separately below
            continue
        if cfg.get("entity"):
            gauge_cards.append(_single_gauge_stack(cfg))

    speed_cfg = _resolve_speed_cfg(server)
    if speed_cfg:
        gauge_cards.append(_dual_speed_stack_card(speed_cfg))

    gauges_grid_full = {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {
            "grid-gap": "8px",
            "padding": "0px",
            "grid-template-columns": f"repeat(auto-fit, minmax({GAUGE_MIN_PX}px, {GAUGE_MAX_PX}px))"
        },
        "cards": gauge_cards,
        "card_mod": CARDMOD_NO_PAD
    }

    # NEW: Compact chips grid
    gauges_grid_compact = _compact_grid_for_server(server)

    # --- Show COMPACT when compact==on & online; FULL when compact==off & online
    gauges_compact_online = {
        "type": "conditional",
        "conditions": [
            {"entity": "input_boolean.gauges_compact", "state": "on"},
            {"entity": f"binary_sensor.{ping}", "state": "on"},
        ],
        "card": gauges_grid_compact,
        "view_layout": {"grid-column": "3"}
    }

    # --- Conditional swap: online -> gauges, offline -> single OFFLINE card
    gauges_full_online = {
        "type": "conditional",
        "conditions": [
            {"entity": "input_boolean.gauges_compact", "state": "off"},
            {"entity": f"binary_sensor.{ping}", "state": "on"},
        ],
        "card": gauges_grid_full,
        "view_layout": {"grid-column": "3"}
    }

    gauges_row_offline = {
        "type": "conditional",
        "conditions": [{"entity": f"binary_sensor.{ping}", "state": "off"}],
        "card": _offline_placeholder_card(server),
        "view_layout": {"grid-column": "3"}
    }

    charts_cards = _build_chart_cards(server, has_swap=_has_swap_gauge(server))
    charts_expander = {
        "type": "custom:expander-card",
        "title-card-button-overlay": True,
        "title-card-clickable": True,
        **EXPANDER_TIGHT,
        "title-card": _row_expander_button(display_name),
        "cards": [_charts_grid_from_cards(charts_cards)],
        "view_layout": {"grid-column": "2 / 4"}
    }

    # return [logo, expander_system, gauges_row, charts_expander]
    return [logo, expander_system, view_toggle, gauges_compact_online, gauges_full_online, gauges_row_offline, charts_expander]

def _logo_card(server: dict) -> dict:
    logo = fnFallbackDefault(server, "logo")
    logo_styles = fnFallbackDefault(server, "title_styles")["logo_card"]
    return {
        "type": "custom:button-card",
        "show_icon": False,
        "show_name": False,
        "show_entity_picture": True,
        "entity_picture": logo,
        "tap_action": _controls_popup_tap_action(server) or {"action": "none"},
        "styles": {
            "card": _button_card_styles(logo_styles.get("card", [])),
            "entity_picture": _button_card_styles(logo_styles.get("entity_picture", [])),
            "img_cell": _button_card_styles(logo_styles.get("img_cell", [])),
        },
    }

def _row_expander_button(name: str) -> dict:
    return {
        "type": "custom:button-card",
        "name": f"{name} – Performance charts",
        "show_icon": False,
        "tap_action": {"action": "none"},
        "styles": {
            "card": [
                {"background": "var(--ha-card-background, var(--card-background-color))"},
                {"border-radius": "12px"},
                {"padding": "10px 14px"},
                {"box-shadow": "0 2px 8px rgba(0,0,0,0.25)"},
                {"font-weight": "600"}
            ]
        }
    }

def build_dashboard(config: dict) -> dict:
    cards_flat = []
    for s in config.get("servers", []):
        cards_flat.extend(server_to_grid_pair(s))

    return {
        "button_card_templates": BUTTON_CARD_TEMPLATES,   # <-- add this
        "views": [{
            "title": "Infrastructure",
            "path": "infra",
            "panel": True,
            "cards": [{
                "type": "custom:layout-card",
                "layout_type": "custom:grid-layout",
                "layout": {
                    "grid-gap": "12px",
                    "grid-auto-rows": "min-content",
                    "grid-template-columns": "120px minmax(280px, max-content) minmax(0, 1fr)",
                    "mediaquery": {"(max-width: 800px)": {"grid-template-columns": "1fr"}}
                },
                "cards": cards_flat
            }]
        }]
    }


def _status_label_js(key: str, ping: str, uptime_sensor: str) -> str:
    # Button-card label (triple-bracket JS) with online/offline/unresponsive handling
    return (
        "[[[\n"
        f"  const pingEnt = states['binary_sensor.{ping}'];\n"
        f"  const upEnt   = states['{uptime_sensor}'];\n"
        "  const pingOn  = pingEnt?.state === 'on';\n"
        "  const upVal   = upEnt ? parseFloat(upEnt.state) : NaN;\n"
        "\n"
        "  function fmtDHMS(secs) {\n"
        "    secs = Math.max(0, secs|0);\n"
        "    const d = Math.floor(secs/86400), h = Math.floor(secs%86400/3600), m = Math.floor(secs%3600/60);\n"
        "    if (d > 0) return `${d}d ${h}h ${m}m`;\n"
        "    if (h > 0) return `${h}h ${m}m`;\n"
        "    return `${m}m`;\n"
        "  }\n"
        "\n"
        "  if (pingOn) {\n"
        "    // Ping is ON → two possibilities: normal (uptime number) or UNRESPONSIVE (uptime NaN)\n"
        "    if (Number.isFinite(upVal) && upVal >= 0) {\n"
        "      return `Uptime: ${fmtDHMS(upVal)}`;\n"
        "    }\n"
        "    // UNRESPONSIVE: ping OK but MQTT uptime missing/NaN\n"
        "    const lc = upEnt?.last_changed || pingEnt?.last_changed;\n"
        "    const since = lc ? (Date.now() - new Date(lc).getTime())/1000 : 0;\n"
        "    return `🟠 Unresponsive · ${fmtDHMS(since)}`;\n"
        "  }\n"
        "\n"
        "  // OFFLINE: ping is OFF\n"
        "  const lc = pingEnt?.last_changed;\n"
        "  if (!lc) return '🔴 Down';\n"
        "  const secs = Math.max(0, (Date.now() - new Date(lc).getTime())/1000);\n"
        "  return `🔴 Down · ${fmtDHMS(secs)}`;\n"
        "]]]"
    )


def build_binary_ping_sensors(config: dict) -> dict | None:
    """
    Build a Home Assistant YAML object that defines a ping-based binary_sensor
    per server that has an 'ip' (preferred) or 'host' field.

    Returns a dict like:
      {"binary_sensor": [{"platform": "ping", "host": "...", "name": "...", ...}, ...]}
    or None if no servers had an IP/host.
    """
    sensors = []
    for s in config.get("servers", []):
        key = s.get("key")
        if not key:
            continue
        host = s.get("ip") or s.get("host")  # support either field name
        if not host:
            continue
        sensors.append({
            "platform": "ping",
            "host": str(host),
            "name": f"{key} Online",
            "count": 2,
            "scan_interval": 30,
        })
    return sensors if sensors else None

def upsert_lovelace_loader(
    loader_file: Path,
    dashboard_id: str,
    *,
    title: str,
    icon: str,
    show_in_sidebar: bool,
    filename_relative_to_ha: str,
) -> None:
    """
    Ensure `loader_file` (dashboards/_dashboards.yaml) has/updates an entry:
      <dashboard_id>:
        mode: yaml
        title: ...
        icon: ...
        show_in_sidebar: true/false
        filename: dashboards/infrastructure.yaml  (path relative to HA config root)

    Creates the file if missing. Replaces existing entry for the same ID.
    """
    loader_file.parent.mkdir(parents=True, exist_ok=True)
    existing = {}

    if loader_file.exists():
        try:
            with loader_file.open("r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
                if not isinstance(existing, dict):
                    print(f"⚠️  {loader_file} is not a mapping; rewriting it cleanly.")
                    existing = {}
        except Exception as e:
            print(f"⚠️  Failed to read {loader_file}: {e}; rewriting it cleanly.")
            existing = {}

    # upsert / replace the specific dashboard entry
    existing[dashboard_id] = {
        "mode": "yaml",
        "title": title,
        "icon": icon,
        "show_in_sidebar": bool(show_in_sidebar),
        "filename": filename_relative_to_ha,
    }

    with loader_file.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, sort_keys=False, allow_unicode=True)
    print(f"✅ Upserted dashboard '{dashboard_id}' in {loader_file}")


def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")

def main():
    parser = argparse.ArgumentParser(description="Generate Lovelace dashboard from JSON config")
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: file {in_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        with open(in_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from {in_path}: {e}", file=sys.stderr)
        sys.exit(1)
    DASH_DIR = OUT_DIR.parent / "dashboards"

    cfg = json.loads(Path(args.input).read_text())
    output_cfg = cfg.get("output", {}) or {}
    # pings_dir = Path(output_cfg.get("pings_dir", Path(args.input).parent / "pings"))
    dashboards_dir = Path(output_cfg.get("dashboards_dir", DASH_DIR / "dashboards"))

    dashboard = build_dashboard(config)
    # Build ping pings YAML
    # ping_yaml = build_binary_ping_sensors(config)
    # PING_FILE = pings_dir / "infrastructure_ping.yaml"

    # if ping_yaml:
    #     if confirm(f"Write ping pings to {PING_FILE}?"):
    #         pings_dir.mkdir(parents=True, exist_ok=True)
    #         PING_FILE.write_text(yaml.dump(ping_yaml, sort_keys=False, allow_unicode=True))
    #         print(f"✅ Wrote {PING_FILE}")
    #     else:
    #         print("↩️  Skipped writing ping pings")
    # else:
    #     print("ℹ️  No servers with 'ip' or 'host' found; skipped ping pings.")

    print("🧱 Create a new dashboard.")
    DASH_FILE = dashboards_dir / "infrastructure.yaml"

    if confirm(f"Write Lovelace dashboard to {DASH_FILE}?"):
        DASH_DIR.mkdir(parents=True, exist_ok=True)
        DASH_FILE.write_text(yaml.dump(dashboard, sort_keys=False, allow_unicode=True))
        print(f"✅ Wrote {DASH_FILE}")
        # print("\nHow to use it:")
        # print("1) In Home Assistant, go to Settings → Dashboards.")
        # print("2) Use YAML mode (or the Raw configuration editor) and load this file.")

        # --- Also ensure the loader (dashboards/_dashboards.yaml) references this file
        dashboard_id   = output_cfg.get("dashboard_id", "infra-dashboard")  # must contain a hyphen
        dashboard_title= output_cfg.get("dashboard_title", "Infrastructure")
        dashboard_icon = output_cfg.get("dashboard_icon", "mdi:server-network")
        show_in_sidebar= bool(output_cfg.get("dashboard_show_in_sidebar", True))

        # Compute filename relative to HA config root (parent of dashboards_dir)
        # Example: dashboards_dir = /var/lib/homeassistant/homeassistant/dashboards
        # -> filename should be "dashboards/infrastructure.yaml"
        ha_config_root = dashboards_dir.parent
        filename_rel   = f"{dashboards_dir.name}/{DASH_FILE.name}"

        # Allow overriding loader path via JSON if you want
        loader_file = Path(output_cfg.get(
            "dashboards_loader",
            str(dashboards_dir / "_dashboards.yaml")  # default: dashboards/_dashboards.yaml
        ))

        if confirm(f"Update dashboards loader at {loader_file} for id '{dashboard_id}'?"):
            upsert_lovelace_loader(
                loader_file,
                dashboard_id,
                title=dashboard_title,
                icon=dashboard_icon,
                show_in_sidebar=show_in_sidebar,
                filename_relative_to_ha=filename_rel,
            )
        else:
            print("↩️  Skipped updating dashboards loader")

    else:
        print("↩️  Skipped writing dashboard file")

    # --- Preflight check & print instructions
    prereq = gather_prereq_findings(config)
    # Emit one shell_commands file per ready server
    write_shell_command_files(config, prereq)

    doc = render_instructions(prereq)
    print("\n" + doc + "\n")        

if __name__ == "__main__":
    main()
