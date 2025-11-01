import argparse
import configparser
import json
import subprocess
import socket
import paho.mqtt.client as mqtt
from pathlib import Path

# ----------------------------------------
# Load MQTT config from Glances .conf
# ----------------------------------------

def load_mqtt_config(conf_path: Path):
    config = configparser.ConfigParser()
    config.read(conf_path)

    if "mqtt" not in config:
        raise ValueError("Missing [mqtt] section in config")

    mqtt_conf = config["mqtt"]
    return {
        "host": mqtt_conf.get("host", "localhost"),
        "port": mqtt_conf.getint("port", 1883),
        "username": mqtt_conf.get("user", None),
        "password": mqtt_conf.get("password", None),
        "topic_prefix": mqtt_conf.get("topic_prefix", "glances"),
        "client_name": socket.gethostname().lower(),
    }

# ----------------------------------------
# Run speedtest-cli and parse output
# ----------------------------------------

def run_speedtest(speedtest_path: str, timeout: int = 60):
    try:
        result = subprocess.run(
            [speedtest_path, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"{speedtest_path} failed with rc={result.returncode}")

        data = json.loads(result.stdout)

        # speedtest-cli JSON: download/upload = bits/sec, ping = ms
        return {
            "download": round(float(data["download"]) / 1e6, 2),  # Mbps
            "upload":   round(float(data["upload"])   / 1e6, 2),  # Mbps
            "ping":     round(float(data["ping"]), 1),            # ms
            "timestamp": data.get("timestamp")
        }
    except Exception as e:
        print(f"Error running speedtest ({speedtest_path}): {e}")
        return None

# ----------------------------------------
# Publish results via MQTT
# ----------------------------------------

def publish_to_mqtt(metrics, mqtt_config):
    client = mqtt.Client()
    if mqtt_config["username"]:
        client.username_pw_set(mqtt_config["username"], mqtt_config["password"])

    client.connect(mqtt_config["host"], mqtt_config["port"], 60)

    topic_base = f"{mqtt_config['topic_prefix']}/{mqtt_config['client_name']}/speedtest"

    for key, value in metrics.items():
        if key == "timestamp":
            continue
        topic = f"{topic_base}/{key}"
        payload = str(value)
        client.publish(topic, payload)
        print(f"Published {key}: {value} → {topic}")

    client.disconnect()

# ----------------------------------------
# Main entry point
# ----------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run speedtest and publish to MQTT using Glances config")
    parser.add_argument("--config", "-C", required=True, help="Path to Glances config file")
    parser.add_argument("--speedtest", "-s", required=True, help="Path to speedtest binary (exe or cli)")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    mqtt_config = load_mqtt_config(config_path)
    metrics = run_speedtest(args.speedtest)
    if metrics:
        publish_to_mqtt(metrics, mqtt_config)
