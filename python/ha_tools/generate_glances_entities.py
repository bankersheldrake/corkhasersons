#!/usr/bin/env python3
"""
Generate Home Assistant MQTT Discovery configs for Glances metrics (paho-mqtt v2)
with robust type inference (numeric / boolean / string).

- Subscribes to <topic_prefix>/# (default 'glances/#') to discover live Glances metrics
- Infers value type from a sample payload to choose correct value_template
- Publishes MQTT Discovery configs (retained) per metric under <discovery_prefix>/sensor/...
- Sets per-host availability topics and publishes 'online' (retained)
- Adds expire_after only for numeric sensors
- Removes stale entities by publishing empty retained /config messages
- Cleanup limited to sensor topics for hosts seen in this run
- --dry-run previews deletions (publishes configs & availability as normal)

Input JSON example:
{
  "mqtt": {"host":"192.168.86.30","port":1883,"username":"u","password":"p"},
  "discovery": {
    "topic_prefix": "glances",
    "discovery_prefix": "homeassistant",
    "availability_prefix": "glances_availability",
    "expire_after": 120
  },
  "output": {
    "sensors_dir": "/config/sensors"
  }
}

Requires: paho-mqtt>=2, pyyaml
"""

import argparse, json, re, time
from pathlib import Path
from typing import Dict, Tuple, List, Set, Optional

import paho.mqtt.client as mqtt
import yaml  # kept for parity
from collections import defaultdict

DEFAULT_PREFIX = "glances"
DEFAULT_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_AVAIL_PREFIX = "glances_availability"
DEFAULT_TIMEOUT = 5
DEFAULT_EXPIRE_AFTER = 120  # seconds

# ---------------- helpers ----------------

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def is_boolish(s: str) -> bool:
    return s.lower() in {"true","false","on","off","1","0"}

def parse_number(s: str):
    try:
        # prefer int when exact
        i = int(s)
        if str(i) == s.strip():
            return i
        # fall back to float
        return float(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None
def prompt_yes_no(msg: str, default: bool = True) -> bool:
    """
    Simple interactive Y/N prompt.
    default=True -> [Y/n]
    default=False -> [y/N]
    """
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        resp = input(msg + suffix + " ").strip().lower()
        if not resp:
            return default
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")

def infer_kind(value: str, tail: str) -> str:
    """
    Return 'number' | 'boolean' | 'string' based on payload and topic tail hints.
    """
    # explicit stringy topics first
    parts = tail.split("/")
    if parts[:2] == ["system", "hostname"]:
        return "string"
    if parts[0] == "system" and len(parts) > 1 and parts[1] in {"os_name","os_version","linux_distro","hr_name","platform"}:
        return "string"

    # try parse booleans
    if is_boolish(value):
        return "boolean"

    # try parse numbers
    if parse_number(value) is not None:
        return "number"

    return "string"

def unit_device_template(topic_tail: str) -> Tuple[str, str, Optional[str], Optional[str], Optional[str]]:
    """
    Decide (unit, device_class, state_class, value_template, entity_category_hint)
    based on tail only. May be overridden by sample-value inference later.
    """
    unit, device_class, state_class, vt, category = "", "", "measurement", "{{ value|float }}", None
    parts = topic_tail.split("/")

    # CPU / MEM / LOAD / UPTIME
    if parts[:2] == ["cpu", "total"]:
        return "%", device_class, state_class, "{{ value|float }}", None
    if parts[:2] == ["mem", "percent"]:
        return "%", device_class, state_class, "{{ value|float }}", None
    if parts[0] == "load" and len(parts) > 1 and parts[1] in ("min1","min5","min15"):
        return "", device_class, state_class, "{{ value|float }}", None
    if parts[:2] == ["uptime", "seconds"]:
        return "s", device_class, state_class, "{{ value|int }}", None

    # FILESYSTEM
    if parts[0] == "fs" and len(parts) >= 3:
        metric = parts[2]
        if metric == "percent":
            return "%", device_class, state_class, "{{ value|float }}", None
        if metric in ("free","used","size"):
            return "GB", "data_size", state_class, "{{ (value|float / 1024**3) | round(2) }}", None

    # NETWORK (rx/tx in KB/s)
    if parts[0] == "network" and len(parts) >= 3 and parts[2] in ("rx","tx"):
        return "KB/s", device_class, state_class, "{{ (value|float / 1024) | round(2) }}", None

    # SENSORS
    if parts[0] == "sensors" and parts[-1] == "value":
        label = "/".join(parts[1:-1]).lower()
        if any(k in label for k in ("temp","thermal","tctl","edge")):
            return "°C", "temperature", state_class, "{{ value|float }}", None
        return "", device_class, state_class, "{{ value|float }}", None

    # SWAP
    if parts[0] == "memswap":
        if len(parts) > 1 and parts[1] == "percent":
            return "%", "", "measurement", "{{ value|float }}", None
        if len(parts) > 1 and parts[1] in ("used", "free", "total"):
            # publish as GB with data_size class (nicer in HA)
            return "GB", "data_size", "measurement", "{{ (value|float / 1024**3) | round(2) }}", None

    # DISK I/O counters
    if parts[0] == "diskio" and len(parts) >= 3:
        metric = parts[2]
        # Bytes are monotonically increasing counters (total bytes since boot)
        if metric in ("read_bytes", "write_bytes"):
            # keep raw bytes with data_size + total_increasing (HA can derive rates)
            return "B", "data_size", "total_increasing", "{{ value|float }}", None
        # Counts are monotonically increasing too
        if metric in ("read_count", "write_count"):
            return "ops", "", "total_increasing", "{{ value|float }}", None

    # Known diagnostics
    if parts[0] == "system" and len(parts) > 1 and parts[1] in {"hostname","os_name","os_version","linux_distro","hr_name","platform"}:
        return "", "", None, "{{ value }}", "diagnostic"

    # default numeric
    return unit, device_class, state_class, "{{ value|float }}", None

def pretty_label(tail: str) -> str:
    p = tail.split("/")
    if p[:2] == ["cpu", "total"]:
        return "CPU"
    if p[:2] == ["mem", "percent"]:
        return "Memory %"
    if p[0] == "load" and len(p) > 1 and p[1] in ("min1","min5","min15"):
        return f"Load ({p[1]})"
    if p[:2] == ["uptime", "seconds"]:
        return "Uptime Seconds"
    if p[0] == "fs":
        mnt = p[1]
        label = "/" if mnt in ("_","") else mnt
        metric = p[2] if len(p) > 2 else ""
        nice = {"percent":"Disk %","free":"Disk / Free","used":"Disk / Used","size":"Disk / Size"}.get(metric, metric)
        return f"{label} {nice}".strip()
    if p[0] == "network" and len(p) >= 3:
        iface, metric = p[1], p[2]
        return f"{iface} {metric.upper()}"
    if p[0] == "sensors" and p[-1] == "value":
        return "/".join(p[1:-1])
    if p[0] == "memswap":
        metric = p[1] if len(p) > 1 else ""
        m = {
            "percent": "Swap %",
            "used": "Swap Used",
            "free": "Swap Free",
            "total": "Swap Total",
        }.get(metric, f"Swap {metric}")
        return m
    if p[0] == "diskio" and len(p) >= 3:
        dev, metric = p[1], p[2]
        m = {
            "read_bytes": "Read Bytes (total)",
            "write_bytes": "Write Bytes (total)",
            "read_count": "Read Ops (total)",
            "write_count": "Write Ops (total)",
        }.get(metric, metric)
        return f"{dev} {m}"
    if p[0] == "system" and len(p) > 1 and p[1] == "hostname":
        return "System hostname"
    return " ".join(p)

def parse_tail(prefix: str, full_topic: str) -> Optional[Tuple[str, str]]:
    if not full_topic.startswith(prefix + "/"):
        return None
    remainder = full_topic[len(prefix) + 1 :]
    bits = remainder.split("/", 1)
    if len(bits) != 2:
        return None
    return bits[0], bits[1]  # host, tail

# ---------------- MQTT helpers ----------------

def mqtt_connect(cfg: dict, client_id: str) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if cfg.get("username"):
        client.username_pw_set(cfg["username"], cfg.get("password", ""))
    if cfg.get("tls"):
        client.tls_set()
    client.connect(cfg.get("host", "localhost"), int(cfg.get("port", 1883)), keepalive=30)
    return client

def mqtt_publish_config(client: mqtt.Client, topic: str, payload: str, retain: bool = True):
    client.publish(topic, payload=payload, qos=0, retain=retain)

def mqtt_delete_config(client: mqtt.Client, topic: str):
    client.publish(topic, payload=None, qos=0, retain=True)

def mqtt_fetch_existing_configs(client: mqtt.Client, prefix: str, timeout_s: float = 2.0) -> Set[str]:
    """Collect retained discovery config topics under <prefix>/# that end with /config."""
    existing: Set[str] = set()
    def _on_message(_c, _u, message):
        if message.topic.endswith("/config"):
            existing.add(message.topic)
    client.on_message = _on_message
    client.loop_start()
    client.subscribe(f"{prefix}/#")
    time.sleep(timeout_s)
    client.loop_stop()
    client.on_message = None
    return existing

# ---------------- script ----------------

def main():
    ap = argparse.ArgumentParser(description="Discover Glances MQTT topics and publish HA MQTT discovery configs.")
    ap.add_argument("--input", "-i", required=True, help="Path to broker config JSON.")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Discovery listen window (seconds).")
    ap.add_argument("--dry-run", action="store_true", help="Preview deletions only (configs & availability still publish).")
    args = ap.parse_args()

    cfg = json.loads(Path(args.input).read_text())
    mqtt_cfg = cfg.get("mqtt", {}) or {}
    disc = cfg.get("discovery", {}) or {}
    prefix = disc.get("topic_prefix", DEFAULT_PREFIX)
    disc_prefix = disc.get("discovery_prefix", DEFAULT_DISCOVERY_PREFIX)
    avail_prefix = disc.get("availability_prefix", DEFAULT_AVAIL_PREFIX)
    expire_after = int(disc.get("expire_after", DEFAULT_EXPIRE_AFTER))
    output_cfg = cfg.get("output", {}) or {}
    sensors_dir = Path(output_cfg.get("sensors_dir", Path(args.input).parent / "sensors"))

    # --- discover current Glances topics ---
    seen: Dict[str, str] = {}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(f"{prefix}/#")
        else:
            print(f"⛔ MQTT connect failed: reason_code={reason_code}")

    def on_message(client, userdata, message):
        seen[message.topic] = message.payload.decode("utf-8", errors="ignore").strip()

    client = mqtt_connect(mqtt_cfg, client_id=f"glances-discover-{int(time.time())}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()
    time.sleep(args.timeout)
    client.loop_stop()

    topics = [t for t in seen if t.startswith(prefix + "/")]
    print(f"Discovered {len(topics)} Glances topics under '{prefix}/#'.")

    desired: Set[str] = set()
    discovered_hosts: Set[str] = set()

    pub = mqtt_connect(mqtt_cfg, client_id=f"glances-publish-{int(time.time())}")
    pub.loop_start()
    try:
        diskio_map = defaultdict(set)  # { shost: {dev1, dev2, ...} }

        for t in sorted(topics):
            parsed = parse_tail(prefix, t)
            if not parsed:
                continue
            host, tail = parsed
            shost = slug(host)
            # Collect diskio devices we saw so we can write YAML later
            if tail.startswith("diskio/"):
                parts = tail.split("/")
                if len(parts) >= 3:
                    dev = parts[1]
                    # ignore loop devices if you like
                    if not re.match(r"^loop", dev):
                        diskio_map[shost].add(dev)

            discovered_hosts.add(shost)

            # Skip noisy docker/bridge interfaces
            if tail.startswith("network/"):
                iface = tail.split("/")[1]
                if iface.startswith(("veth","docker","br-","virbr","zt")):
                    continue

            sample_value = seen.get(t, "")
            kind = infer_kind(sample_value, tail)

            unit, device_class, state_class, vt, category = unit_device_template(tail)

            # Override by inferred kind where necessary
            if kind == "string":
                vt = "{{ value }}"
                state_class = None
                # keep explicit units only if truly meaningful (already handled above)
            elif kind == "boolean":
                # normalize to on/off as string
                vt = "{{ 'on' if value|lower in ['true','on','1'] else 'off' }}"
                state_class = None
                device_class = ""  # could choose 'power' etc., but generic is fine
                unit = ""

            # ---- stable IDs ----
            object_id = f"{shost}_{slug(tail)}"   # entity_id base (sensor.<object_id>)
            unique_id = object_id                 # persistent unique id for HA

            name = pretty_label(tail)

            # per-host availability (retained)
            avail_topic = f"{avail_prefix}/{shost}"
            pub.publish(avail_topic, payload="online", qos=0, retain=True)

            # Discovery config (sensor)
            cfg_topic = f"{disc_prefix}/sensor/{shost}/{object_id}/config"
            cfg_payload = {
                "name": name,               # no host prefix
                "object_id": object_id,     # controls entity_id base
                "unique_id": unique_id,     # persistent
                "state_topic": t,
                "value_template": vt,
                "device": {
                    "identifiers": [f"glances_{shost}"],
                    "name": host,
                    "manufacturer": "Glances",
                    "model": "Glances MQTT Export",
                },
                "availability": [{
                    "topic": avail_topic,
                    "payload_available": "online",
                    "payload_not_available": "offline"
                }],
            }
            if unit:
                cfg_payload["unit_of_measurement"] = unit
            if device_class:
                cfg_payload["device_class"] = device_class
            if state_class:
                cfg_payload["state_class"] = state_class
            if category:
                cfg_payload["entity_category"] = category

            # expire_after only for numeric sensors (strings often don't change)
            if kind == "number" and expire_after > 0:
                cfg_payload["expire_after"] = expire_after

            mqtt_publish_config(pub, cfg_topic, json.dumps(cfg_payload), retain=True)
            desired.add(cfg_topic)

        print(f"Published {len(desired)} discovery configs under '{disc_prefix}/sensor/.../config'.")

        # --- cleanup stale configs (safe) ---
        existing = mqtt_fetch_existing_configs(pub, disc_prefix, timeout_s=2.0)
        safe_prefixes = tuple(f"{disc_prefix}/sensor/{h}/" for h in sorted(discovered_hosts))
        candidates = {t for t in existing if t.startswith(safe_prefixes)}
        stale = candidates - desired

        if stale:
            print(f"[cleanup] Found {len(stale)} stale discovery topics.")
        else:
            print("[cleanup] No stale discovery topics.")

        for s in sorted(stale):
            if args.dry_run:
                print(f"[cleanup] (dry-run) Would delete: {s}")
            else:
                print(f"[cleanup] Deleting: {s}")
                mqtt_delete_config(pub, s)
        # --- write per-host disk I/O derived sensors (MB/s + IOPS) ---
        if diskio_map:
            sensors_dir.mkdir(parents=True, exist_ok=True)

            print(f"\nAbout to generate {len(diskio_map)} sensor file(s) in: {sensors_dir / 'diskio'}")
            save_files = prompt_yes_no("Save new sensor files to disk?", default=True)

            if save_files:
                # ensure subfolder + loader exist or will be created
                diskio_dir = sensors_dir / "diskio"
                diskio_dir.mkdir(parents=True, exist_ok=True)

                clear_first = prompt_yes_no(
                    f"Clear existing YAML files in {diskio_dir} first?",
                    default=False
                )
                if clear_first:
                    removed = 0
                    for p in diskio_dir.glob("*.yaml"):
                        try:
                            p.unlink()
                            removed += 1
                        except Exception as e:
                            print(f"⚠️  Could not delete {p}: {e}")
                    print(f"🧹 Cleared {removed} existing file(s) from {diskio_dir}.")

                for shost, devices in sorted(diskio_map.items()):
                    payload = []             # list of platforms (derivative + template)
                    template_sensors = {}    # name -> dict for "platform: template"

                    for dev in sorted(devices):
                        dev_slug = slug(dev)

                        # raw MQTT-discovered counter entity_ids (your pattern)
                        read_bytes_e = f"sensor.{shost}_diskio_{dev_slug}_read_bytes"
                        write_bytes_e = f"sensor.{shost}_diskio_{dev_slug}_write_bytes"
                        read_count_e = f"sensor.{shost}_diskio_{dev_slug}_read_count"
                        write_count_e = f"sensor.{shost}_diskio_{dev_slug}_write_count"

                        # ---- live rates (Recorder not required) using DERIVATIVE ----
                        # Bytes/sec and ops/sec computed over a 2-minute window, rounded as in your manual example
                        payload += [
                            {
                                "platform": "derivative",
                                "name": f"{shost}_{dev_slug}_read_bps",
                                # "unique_id": f"glances_derived_{shost}_{dev_slug}_read_bps",
                                "source": read_bytes_e,
                                "unit_time": "s",
                                "time_window": """00:02:00""",
                                "round": 2,
                            },
                            {
                                "platform": "derivative",
                                "name": f"{shost}_{dev_slug}_write_bps",
                                # "unique_id": f"glances_derived_{shost}_{dev_slug}_write_bps",
                                "source": write_bytes_e,
                                "unit_time": "s",
                                "time_window": """00:02:00""",
                                "round": 2,
                            },
                            {
                                "platform": "derivative",
                                "name": f"{shost}_{dev_slug}_read_iops",
                                # "unique_id": f"glances_derived_{shost}_{dev_slug}_read_iops",
                                "source": read_count_e,
                                "unit_time": "s",
                                "time_window": """00:02:00""",
                                "round": 2,
                            },
                            {
                                "platform": "derivative",
                                "name": f"{shost}_{dev_slug}_write_iops",
                                # "unique_id": f"glances_derived_{shost}_{dev_slug}_write_iops",
                                "source": write_count_e,
                                "unit_time": "s",
                                "time_window": """00:02:00""",
                                "round": 2,
                            },
                        ]

                        # references to the just-created derivative sensors
                        read_bps = f"sensor.{shost}_{dev_slug}_read_bps"
                        write_bps = f"sensor.{shost}_{dev_slug}_write_bps"
                        read_iops = f"sensor.{shost}_{dev_slug}_read_iops"
                        write_iops = f"sensor.{shost}_{dev_slug}_write_iops"

                        # ---- derived display sensors (MB/s and total IOPS) ----
                        template_sensors[f"{shost}_{dev_slug}_read_mb_s"] = {
                            "friendly_name": f"{shost} {dev} Read MB/s",
                            "unit_of_measurement": "MB/s",
                            "state_class": "measurement",
                            "unique_id": f"glances_template_{shost}_{dev_slug}_read_mb_s",
                            "value_template": "{{ (states('%s')|float(0) / 1048576) | round(2) }}" % read_bps,
                        }
                        template_sensors[f"{shost}_{dev_slug}_write_mb_s"] = {
                            "friendly_name": f"{shost} {dev} Write MB/s",
                            "unit_of_measurement": "MB/s",
                            "state_class": "measurement",
                            "unique_id": f"glances_template_{shost}_{dev_slug}_write_mb_s",
                            "value_template": "{{ (states('%s')|float(0) / 1048576) | round(2) }}" % write_bps,
                        }
                        template_sensors[f"{shost}_{dev_slug}_throughput_mb_s"] = {
                            "friendly_name": f"{shost} {dev} Throughput MB/s",
                            "unit_of_measurement": "MB/s",
                            "state_class": "measurement",
                            "unique_id": f"glances_template_{shost}_{dev_slug}_throughput_mb_s",
                            "value_template": (
                                "{{ ((states('%s')|float(0) + states('%s')|float(0)) / 1048576) | round(2) }}"
                                % (read_bps, write_bps)
                            ),
                        }
                        template_sensors[f"{shost}_{dev_slug}_iops"] = {
                            "friendly_name": f"{shost} {dev} IOPS",
                            "unit_of_measurement": "ops/s",
                            "state_class": "measurement",
                            "unique_id": f"glances_template_{shost}_{dev_slug}_iops",
                            "value_template": "{{ (states('%s')|float(0) + states('%s')|float(0)) | round(1) }}" % (read_iops, write_iops),
                        }

                    if template_sensors:
                        payload.append({"platform": "template", "sensors": template_sensors})

                    out_path = diskio_dir / f"{shost}.yaml"
                    with open(out_path, "w", encoding="utf-8") as f:
                        yaml.dump(payload, f, sort_keys=False, allow_unicode=True, width=120)
                    print(f"📝 Wrote {out_path} for {len(devices)} device(s).")

                # Ensure top-level loader exists/updated (no leading dash!)
                loader_path = sensors_dir / "diskio_loader.yaml"
                desired_loader = "!include_dir_merge_list sensors/diskio\n"
                try:
                    current = loader_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    current = ""
                if current.strip() != desired_loader.strip():
                    loader_path.write_text(desired_loader, encoding="utf-8")
                    print(f"📝 Wrote loader file {loader_path}")
                else:
                    print(f"✓ Loader already correct: {loader_path}")
            else:
                print("Skipped writing sensor files.")

    finally:
        pub.loop_stop()
        pub.disconnect()

if __name__ == "__main__":
    main()
