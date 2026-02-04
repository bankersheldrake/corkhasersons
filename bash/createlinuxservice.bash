#!/usr/bin/env bash
#
# createlinuxservice_v2.sh
#
# Create a KB-compliant ecosystem Linux service using the
# wrapper.service + optional wrapper.path execution model.
#

set -euo pipefail

# ============================================================
# Fixed ecosystem paths (AUTHORITATIVE)
# ============================================================
SYSTEMD_DIR="/etc/systemd/system"
SERVICES_DIR="/usr/services"

WRAPPER_SERVICE_EXEC="/usr/services/service_exec.sh"
WRAPPER_SERVICE_STOP="/usr/services/service_stop.sh"
STANDARD_MAIN="/usr/services/lib/standard_service_main.sh"

TARGET_SCRIPT_NAME="start.sh"

# ============================================================
# Inputs
# ============================================================
JOB_NAME=""
RUN_AS_USER=""
WATCH_EXTRA_PATHS=""

DRY_RUN=0
AUTO_YES=0
AUTO_DEFAULTS=0
CONFIG_FILE=""
SAVE_CONFIG_PATH=""
SAVED_CONFIG_ACTUAL=""

SERVICE_MODE=""          # always | interval | daily
INTERVAL_SECONDS=""      # for interval mode
DAILY_TIME=""            # for daily mode (HH:MM)
PROMPTED=false

HARDENING_MODE=""   # ephemeral UX choice: locked | none | custom
HARDEN_NO_NEW_PRIVS=""
HARDEN_PRIVATE_TMP=""
HARDEN_PROTECT_SYSTEM=""
HARDEN_PROTECT_HOME=""

# Persisted raw UX inputs (menu selector strings)
AFTER_SELECT_RAW=""     # e.g. "1,3"
DEPS_SELECT_RAW=""      # e.g. "2,5"
DEP_MODE_RAW=""         # "1" or "2" exactly as entered (optional)

AFTER_UNITS=()
WANTS_UNITS=()
REQUIRES_UNITS=()

# ============================================================
# Helpers
# ============================================================
die()  { echo "[ERROR] $*" >&2; exit 1; }
warn() { echo "[WARN]  $*" >&2; }

#is_tty() { [[ -t 0 && -t 1 ]]; }
is_tty() { [[ -t 0 ]]; }

run_cmd() {
  echo "+ $*"
  [[ "$DRY_RUN" -eq 0 ]] && "$@"
}
dedupe_array() {
  local -n arr="$1"
  mapfile -t arr < <(printf "%s\n" "${arr[@]}" | sort -u)
}
write_file() {
  local path="$1"
  local content="$2"
  echo "+ write: $path"
  [[ "$DRY_RUN" -eq 0 ]] && printf '%s\n' "$content" > "$path"
}

append_file() {
  local path="$1"
  local content="$2"
  echo "+ append: $path"
  [[ "$DRY_RUN" -eq 0 ]] && printf '%s\n' "$content" >> "$path"
}

prompt_if_empty() {
  local var="$1" prompt="$2" default="${3:-}"

  # Pattern B:
  # - If default is provided, we PROMPT even if variable is already set
  # - If no default is provided, existing value is authoritative
  if [[ -n "${!var:-}" && -z "$default" ]]; then
    return 0
  fi

  is_tty || return 0

  if [[ "${AUTO_DEFAULTS:-0}" -eq 1 && -n "$default" ]]; then
    printf -v "$var" '%s' "$default"
    return 0
  fi

  local v=""
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " v
    v="${v:-$default}"
  else
    read -r -p "$prompt: " v
  fi

  printf -v "$var" '%s' "$v"
}

normalize_bool() {
  case "${1,,}" in
    y|yes|true|1) echo "yes" ;;
    n|no|false|0) echo "no" ;;
    *) die "Invalid boolean value: $1 (expected yes/no)" ;;
  esac
}

confirm_or_exit() {
  [[ "$AUTO_YES" -eq 1 ]] && return 0
  is_tty || return 0

  read -r -p "Proceed to create/update systemd units and target script? [y/N]: " a
  [[ "${a,,}" == "y" || "${a,,}" == "yes" ]] || die "Aborted by user"
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Must be run as root (via sudo)"
}

require_files() {
  [[ -f "$WRAPPER_SERVICE_EXEC" ]] || die "Missing: $WRAPPER_SERVICE_EXEC"
  [[ -f "$WRAPPER_SERVICE_STOP" ]] || die "Missing: $WRAPPER_SERVICE_STOP"
  [[ -f "$STANDARD_MAIN" ]]        || die "Missing: $STANDARD_MAIN"
}

DEPENDENCY_CATALOG=(
  "network.target"
  "network-online.target"
  "docker.service"
  "mariadb.service"
  "postgresql.service"
  "redis.service"
  "influxdb.service"
  "mqtt.service"
  "tailscaled.service"
  "remote-fs.target"
)

prompt_dependency_units() {
  local prompt="$1"
  local __resultvar="$2"          # array var name to populate with unit names
  local default_raw="${3:-}"      # persisted raw selector string (e.g. "1,3")
  local __rawvar="${4:-}"         # var name to store raw selector input

  local choices=("${DEPENDENCY_CATALOG[@]}")

  echo
  echo "$prompt"
  echo

  local i=1
  for u in "${choices[@]}"; do
    printf "  [%d] %s\n" "$i" "$u"
    ((i++))
  done

  echo
  echo "Enter number or comma-separated list (ENTER = none)"
  [[ -n "$default_raw" ]] && echo "Default: $default_raw"
  echo

  local input=""
  read -r -p "> " input

  # ------------------------------------------------------------
  # Apply inferred default if ENTER pressed
  # ------------------------------------------------------------
  if [[ -z "$input" ]]; then
    input="$default_raw"
  fi

  # ------------------------------------------------------------
  # Persist RAW selector exactly as entered or defaulted
  # ------------------------------------------------------------
  if [[ -n "$__rawvar" ]]; then
    printf -v "$__rawvar" '%s' "$input"
  fi

  # ------------------------------------------------------------
  # Empty selection = no units
  # ------------------------------------------------------------
  [[ -z "$input" ]] && return 0

  # ------------------------------------------------------------
  # Normalize for parsing ONLY
  # ------------------------------------------------------------
  local input_norm="${input//[[:space:]]/}"

  local selected=()
  local nums=()
  IFS=',' read -r -a nums <<< "$input_norm"

  for n in "${nums[@]}"; do
    [[ "$n" =~ ^[0-9]+$ ]] || die "Invalid selection: '$n' (must be numeric)"

    if (( n < 1 || n > ${#choices[@]} )); then
      die "Selection out of range: $n"
    fi

    selected+=("${choices[$((n-1))]}")
  done

  # ------------------------------------------------------------
  # Assign resolved unit names to caller array
  # ------------------------------------------------------------
  eval "$__resultvar+=(\"\${selected[@]}\")"
}

prompt_service_dependencies() {

  # ------------------------------------------------------------
  # Infer defaults from RAW state
  # ------------------------------------------------------------
  local default_has_prereqs="no"
  [[ -n "$AFTER_SELECT_RAW" || -n "$DEPS_SELECT_RAW" ]] && default_has_prereqs="yes"

  prompt_if_empty HAS_PREREQS \
    "Does this service depend on other system components being ready? (yes/no)" \
    "$default_has_prereqs"

  HAS_PREREQS="$(normalize_bool "$HAS_PREREQS")"
  [[ "$HAS_PREREQS" == "no" ]] && return 0

  # ------------------------------------------------------------
  # Ordering-only dependencies (After=)
  # ------------------------------------------------------------
  local default_needs_ordering="no"
  [[ -n "$AFTER_SELECT_RAW" ]] && default_needs_ordering="yes"

  prompt_if_empty NEEDS_ORDERING \
    "Should startup wait until something has started first? (ordering only) (yes/no)" \
    "$default_needs_ordering"

  NEEDS_ORDERING="$(normalize_bool "$NEEDS_ORDERING")"

  if [[ "$NEEDS_ORDERING" == "yes" ]]; then
    prompt_dependency_units \
      "Select units to wait for (After=):" \
      AFTER_UNITS \
      "$AFTER_SELECT_RAW" \
      AFTER_SELECT_RAW
  else
    AFTER_SELECT_RAW=""
  fi

  # ------------------------------------------------------------
  # Availability dependencies (Wants=/Requires=)
  # ------------------------------------------------------------
  local default_needs_dependency="no"
  [[ -n "$DEPS_SELECT_RAW" ]] && default_needs_dependency="yes"

  prompt_if_empty NEEDS_DEPENDENCY \
    "Should this service only start if another service is available? (yes/no)" \
    "$default_needs_dependency"

  NEEDS_DEPENDENCY="$(normalize_bool "$NEEDS_DEPENDENCY")"
  [[ "$NEEDS_DEPENDENCY" == "no" ]] && return 0

  # ------------------------------------------------------------
  # Dependency mode (desired vs mandatory)
  # ------------------------------------------------------------
  echo
  echo "Is the dependency mandatory or just desired?"
  echo
  echo "  [1] Desired   (recommended – service may still run)"
  echo "  [2] Mandatory (NOT recommended unless absolutely required)"
  echo

  local default_dep_mode="${DEP_MODE_RAW:-1}"
  local dep_mode=""
  read -r -p "Enter choice [1/2] (default ${default_dep_mode}): " dep_mode
  dep_mode="${dep_mode:-$default_dep_mode}"
  DEP_MODE_RAW="$dep_mode"

  if [[ "$dep_mode" == "2" ]]; then
    echo
    warn "Using Requires= strongly couples service startup."
    warn "This can cause boot delays or failures."
    warn "NEVER use Requires=network-online.target unless you fully understand the impact."
    echo
  fi

  # ------------------------------------------------------------
  # Dependency unit selection
  # ------------------------------------------------------------
  prompt_dependency_units \
    "Select dependency units:" \
    SELECTED_DEPS \
    "$DEPS_SELECT_RAW" \
    DEPS_SELECT_RAW

  # ------------------------------------------------------------
  # Derive systemd semantics (ephemeral)
  # ------------------------------------------------------------
  for u in "${SELECTED_DEPS[@]}"; do
    if [[ "$dep_mode" == "2" ]]; then
      if [[ "$u" == "network-online.target" ]]; then
        warn "Requires=network-online.target is usually a design error."
        warn "Continuing anyway as requested."
      fi

      REQUIRES_UNITS+=("$u")
      AFTER_UNITS+=("$u")
    else
      WANTS_UNITS+=("$u")
      AFTER_UNITS+=("$u")
    fi
  done

  dedupe_array AFTER_UNITS
  dedupe_array WANTS_UNITS
  dedupe_array REQUIRES_UNITS
}


# ============================================================
# Service run mode prompt (TTY-safe)
# ============================================================
prompt_service_mode() {
  SERVICE_MODE="${SERVICE_MODE:-always}"

  local default="$SERVICE_MODE"

  # Pattern B:
  # - If no default exists, existing value is authoritative
  [[ -n "$SERVICE_MODE" && -z "$default" ]] && return 0

  is_tty || return 0

  if [[ "${AUTO_DEFAULTS:-0}" -eq 1 && -n "$default" ]]; then
    SERVICE_MODE="$default"
    return 0
  fi

  echo
  echo "Choose how the service should run:"
  echo "  [1] Always running (auto-restarts on failure)"
  echo "  [2] Scheduled every X seconds (e.g. every 600s)"
  echo "  [3] Run once per day at specific time (e.g. 03:15)"
  echo

  local choice=""
  read -r -p "Enter choice [1/2/3] (default ${default}): " choice
  choice="${choice:-$default}"

  case "$choice" in
    1|always)
      SERVICE_MODE="always"
      ;;
    2|interval)
      SERVICE_MODE="interval"
      read -r -p "Enter interval in seconds (e.g. 900): " INTERVAL_SECONDS
      [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || die "Interval must be numeric"
      ;;
    3|daily)
      SERVICE_MODE="daily"
      read -r -p "Enter time of day (HH:MM, 24h): " DAILY_TIME
      [[ "$DAILY_TIME" =~ ^[0-2][0-9]:[0-5][0-9]$ ]] || die "Invalid time format"
      ;;
    *)
      die "Invalid service mode selection"
      ;;
  esac

  PROMPTED=true
}

prompt_hardening_mode() {
  # Ephemeral UX choice only
  HARDENING_MODE="${HARDENING_MODE:-locked}"
  local default="$HARDENING_MODE"

  is_tty || return 0

  if [[ "${AUTO_DEFAULTS:-0}" -eq 1 ]]; then
    HARDENING_MODE="$default"
  else
    echo
    echo "How secure do you want the service?"
    echo "  [1] Locked down   (recommended defaults)"
    echo "  [2] No hardening  (fully permissive)"
    echo "  [3] Custom        (choose options individually)"
    echo

    local choice=""
    read -r -p "Enter choice [1/2/3] (default ${default}): " choice
    choice="${choice:-$default}"

    case "$choice" in
      1|locked) HARDENING_MODE="locked" ;;
      2|none)   HARDENING_MODE="none" ;;
      3|custom) HARDENING_MODE="custom" ;;
      *) die "Invalid hardening selection" ;;
    esac
  fi

  # ------------------------------------------------------------
  # Apply presets or prompt for custom values
  # ------------------------------------------------------------
  case "$HARDENING_MODE" in
    locked)
      HARDEN_NO_NEW_PRIVS="yes"
      HARDEN_PRIVATE_TMP="yes"
      HARDEN_PROTECT_SYSTEM="yes"
      HARDEN_PROTECT_HOME="yes"
      ;;
    none)
      HARDEN_NO_NEW_PRIVS="no"
      HARDEN_PRIVATE_TMP="no"
      HARDEN_PROTECT_SYSTEM="no"
      HARDEN_PROTECT_HOME="no"
      ;;
    custom)
      prompt_if_empty HARDEN_NO_NEW_PRIVS \
        "Enable NoNewPrivileges? Prevents privilege escalation (blocks setuid, sudo, file caps). May break tools needing elevation." \
        "${HARDEN_NO_NEW_PRIVS:-yes}"

      prompt_if_empty HARDEN_PRIVATE_TMP \
        "Enable PrivateTmp? Isolates /tmp and /var/tmp for this service. May break shared-temp workflows." \
        "${HARDEN_PRIVATE_TMP:-yes}"

      prompt_if_empty HARDEN_PROTECT_SYSTEM \
        "Protect system files? Makes OS paths read-only to the service. May break services writing system paths." \
        "${HARDEN_PROTECT_SYSTEM:-yes}"

      prompt_if_empty HARDEN_PROTECT_HOME \
        "Protect home directories? Restricts access to /home. May break user-scoped services." \
        "${HARDEN_PROTECT_HOME:-yes}"
      ;;
  esac

  # ------------------------------------------------------------
  # Normalize to systemd-valid booleans (authoritative)
  # ------------------------------------------------------------
  HARDEN_NO_NEW_PRIVS="$(normalize_bool "$HARDEN_NO_NEW_PRIVS")"
  HARDEN_PRIVATE_TMP="$(normalize_bool "$HARDEN_PRIVATE_TMP")"
  HARDEN_PROTECT_SYSTEM="$(normalize_bool "$HARDEN_PROTECT_SYSTEM")"
  HARDEN_PROTECT_HOME="$(normalize_bool "$HARDEN_PROTECT_HOME")"
}

infer_hardening_mode() {
  # Only infer if all values are set (i.e. coming from config)
  [[ -z "${HARDEN_NO_NEW_PRIVS:-}" ]] && return 0
  [[ -z "${HARDEN_PRIVATE_TMP:-}" ]] && return 0
  [[ -z "${HARDEN_PROTECT_SYSTEM:-}" ]] && return 0
  [[ -z "${HARDEN_PROTECT_HOME:-}" ]] && return 0

  if [[ "$HARDEN_NO_NEW_PRIVS"   == "yes" &&
        "$HARDEN_PRIVATE_TMP"    == "yes" &&
        "$HARDEN_PROTECT_SYSTEM" == "yes" &&
        "$HARDEN_PROTECT_HOME"   == "yes" ]]; then
    HARDENING_MODE="locked"
    return 0
  fi

  if [[ "$HARDEN_NO_NEW_PRIVS"   == "no" &&
        "$HARDEN_PRIVATE_TMP"    == "no" &&
        "$HARDEN_PROTECT_SYSTEM" == "no" &&
        "$HARDEN_PROTECT_HOME"   == "no" ]]; then
    HARDENING_MODE="none"
    return 0
  fi

  HARDENING_MODE="custom"
}

parse_kv_config() {
  local f="$1"
  [[ -f "$f" ]] || die "Config not found: $f"
  while IFS= read -r l || [[ -n "$l" ]]; do
    l="${l%%#*}"
    l="${l#"${l%%[![:space:]]*}"}"
    [[ -z "$l" ]] && continue
    [[ "$l" =~ ^([^=]+)=(.*)$ ]] || continue
    k="${BASH_REMATCH[1]}"
    v="${BASH_REMATCH[2]}"
    case "$k" in
      job)                [[ -z "$JOB_NAME" ]] && JOB_NAME="$v" ;;
      run_as)             [[ -z "$RUN_AS_USER" ]] && RUN_AS_USER="$v" ;;
      watch_extra)        [[ -z "$WATCH_EXTRA_PATHS" ]] && WATCH_EXTRA_PATHS="$v" ;;
      service_mode)       [[ -z "$SERVICE_MODE" ]] && SERVICE_MODE="$v" ;;
      interval_seconds)   [[ -z "$INTERVAL_SECONDS" ]] && INTERVAL_SECONDS="$v" ;;
      daily_time)         [[ -z "$DAILY_TIME" ]] && DAILY_TIME="$v" ;;
	  dry_run)
	    if [[ "$v" =~ ^(1|true|yes)$ ]]; then
		  DRY_RUN=1
	    fi
	    ;;
	  auto_defaults)
	    if [[ "$v" =~ ^(1|true|yes)$ ]]; then
	  	  AUTO_DEFAULTS=1
	    fi
	    ;;
	  harden_no_new_privs)   [[ -z "$HARDEN_NO_NEW_PRIVS" ]] && HARDEN_NO_NEW_PRIVS="$v" ;;
	  harden_private_tmp)   [[ -z "$HARDEN_PRIVATE_TMP" ]] && HARDEN_PRIVATE_TMP="$v" ;;
	  harden_protect_system)[[ -z "$HARDEN_PROTECT_SYSTEM" ]] && HARDEN_PROTECT_SYSTEM="$v" ;;
	  harden_protect_home)  [[ -z "$HARDEN_PROTECT_HOME" ]] && HARDEN_PROTECT_HOME="$v" ;;
	after_select_raw)
	  [[ -z "$AFTER_SELECT_RAW" ]] && AFTER_SELECT_RAW="$v"
	  ;;
	deps_select_raw)
	  [[ -z "$DEPS_SELECT_RAW" ]] && DEPS_SELECT_RAW="$v"
	  ;;
	dep_mode_raw)
	  [[ -z "$DEP_MODE_RAW" ]] && DEP_MODE_RAW="$v"
	  ;;

    esac
  done < "$f"
  
  ORIG_JOB_NAME="$JOB_NAME"
  ORIG_RUN_AS_USER="$RUN_AS_USER"
  ORIG_WATCH_EXTRA_PATHS="$WATCH_EXTRA_PATHS"
  ORIG_SERVICE_MODE="$SERVICE_MODE"
  ORIG_INTERVAL_SECONDS="$INTERVAL_SECONDS"
  ORIG_DAILY_TIME="$DAILY_TIME"
  ORIG_HARDEN_NO_NEW_PRIVS="$HARDEN_NO_NEW_PRIVS"
  ORIG_HARDEN_PRIVATE_TMP="$HARDEN_PRIVATE_TMP"
  ORIG_HARDEN_PROTECT_SYSTEM="$HARDEN_PROTECT_SYSTEM"
  ORIG_HARDEN_PROTECT_HOME="$HARDEN_PROTECT_HOME"
  ORIG_AFTER_SELECT_RAW="$AFTER_SELECT_RAW"
ORIG_DEPS_SELECT_RAW="$DEPS_SELECT_RAW"
ORIG_DEP_MODE_RAW="$DEP_MODE_RAW"

  
}

save_effective_config() {
  local p="$1"
  echo "+ saved config: $p"
  [[ "$DRY_RUN" -eq 0 ]] && cat > "$p" <<EOF
job=$JOB_NAME
run_as=$RUN_AS_USER
watch_extra=$WATCH_EXTRA_PATHS
service_mode=$SERVICE_MODE
interval_seconds=$INTERVAL_SECONDS
daily_time=$DAILY_TIME
auto_defaults=$AUTO_DEFAULTS
dry_run=$DRY_RUN
harden_no_new_privs=$HARDEN_NO_NEW_PRIVS
harden_private_tmp=$HARDEN_PRIVATE_TMP
harden_protect_system=$HARDEN_PROTECT_SYSTEM
harden_protect_home=$HARDEN_PROTECT_HOME
after_select_raw=$AFTER_SELECT_RAW
deps_select_raw=$DEPS_SELECT_RAW
dep_mode_raw=$DEP_MODE_RAW

EOF
  SAVED_CONFIG_ACTUAL="$p"
}

target_dir()    { echo "$SERVICES_DIR/$JOB_NAME"; }
target_script() { echo "$(target_dir)/$TARGET_SCRIPT_NAME"; }

prompt_save_config() {
  is_tty || return 0

  echo
  echo "Configuration changes detected."
  echo
  echo "Choose how to save the updated configuration:"
  echo "  [1] Overwrite existing config"
  echo "  [2] Save to a new config file"
  echo "  [3] Do not save changes"
  echo

  read -r -p "Enter choice [1/2/3] (default 3): " choice
  choice="${choice:-3}"

  case "$choice" in
    1)
      save_effective_config "$CONFIG_FILE"
      ;;
    2)
      save_effective_config "$SAVE_CONFIG_PATH"
      ;;
    *)
      echo "Config changes not saved."
      ;;
  esac
}


# ============================================================
# Argument parsing
# ============================================================
for arg in "$@"; do
  case "$arg" in
    --job=*) JOB_NAME="${arg#*=}" ;;
    --run-as=*) RUN_AS_USER="${arg#*=}" ;;
    --watch-extra=*) WATCH_EXTRA_PATHS="${arg#*=}" ;;
    --config=*) CONFIG_FILE="${arg#*=}" ;;
    --save-config=*) SAVE_CONFIG_PATH="${arg#*=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --yes) AUTO_YES=1 ;;
    --auto-defaults) AUTO_DEFAULTS=1 ;;
    --service-mode=*) SERVICE_MODE="${arg#*=}" ;;
    --interval-seconds=*) INTERVAL_SECONDS="${arg#*=}" ;;
    --daily-time=*) DAILY_TIME="${arg#*=}" ;;
    --help|-h)
      cat <<EOF
Usage:
  sudo $0 [--config=file] [--job=name] [--run-as=user] [--watch-extra=p1;p2]

Notes:
  - Interactive ENTER for run-as defaults to sudo caller
  - Watcher path unit is only created if watch paths are provided
EOF
      exit 0
      ;;
  esac
done

# ============================================================
# Load config + prompts
# ============================================================
require_root
require_files

[[ -n "$CONFIG_FILE" ]] && parse_kv_config "$CONFIG_FILE"

prompt_if_empty JOB_NAME "Enter job name" "$JOB_NAME"
# ============================================================
# Validate job name
# ============================================================
[[ -n "$JOB_NAME" ]] || die "--job is required"

if [[ ! "$JOB_NAME" =~ ^[a-z0-9][a-z0-9._@-]*$ ]]; then
  die "Invalid job name: '$JOB_NAME'
Rules:
  - must start with a lowercase letter or digit
  - may contain only: a–z 0–9 . _ @ -
  - no spaces, slashes, or special characters"
fi

case "$JOB_NAME" in
  .|..) die "Invalid job name: '$JOB_NAME' (reserved name)" ;;
esac

prompt_service_mode

prompt_if_empty RUN_AS_USER \
  "Run service as user (ENTER = sudo caller: ${SUDO_USER:-root})" "$RUN_AS_USER"
if [[ "$SERVICE_MODE" == "always" ]]; then
  prompt_if_empty WATCH_EXTRA_PATHS \
    "Extra watch paths (semicolon-separated, blank = none)" \
    "$WATCH_EXTRA_PATHS"
fi


if [[ -z "$WATCH_EXTRA_PATHS" ]]; then
  WATCH_EXTRA_PATHS="__NONE__"
fi

HAS_WATCH_PATHS=true

if [[ "$WATCH_EXTRA_PATHS" == "__NONE__" ]]; then
  HAS_WATCH_PATHS=false
elif [[ -z "$WATCH_EXTRA_PATHS" ]]; then
  HAS_WATCH_PATHS=false
fi
  
# ============================================================
# Resolve run-as user (sudo-aware, AUTHORITATIVE)
# ============================================================
if [[ -z "$RUN_AS_USER" ]]; then
  if is_tty && [[ -n "${SUDO_USER:-}" ]]; then
    RUN_AS_USER="$SUDO_USER"
  else
    RUN_AS_USER="root"
  fi
fi

# ============================================================
# Validation
# ============================================================
[[ "$JOB_NAME" =~ ^[a-zA-Z0-9._@-]+$ ]] || die "Invalid job name: $JOB_NAME"
id "$RUN_AS_USER" >/dev/null 2>&1 || die "Run-as user does not exist: $RUN_AS_USER"

[[ -z "$SAVE_CONFIG_PATH" ]] && \
  SAVE_CONFIG_PATH="/tmp/${JOB_NAME}_service_$(date +%Y%m%d_%H%M%S).config"

# ============================================================
# Validate service run mode
# ============================================================
SERVICE_MODE="${SERVICE_MODE:-always}"

case "$SERVICE_MODE" in
  always)   : ;;
  interval) [[ -n "$INTERVAL_SECONDS" ]] || die "interval mode requires INTERVAL_SECONDS" ;;
  daily)    [[ -n "$DAILY_TIME" ]] || die "daily mode requires DAILY_TIME" ;;
  *)        die "Invalid SERVICE_MODE: $SERVICE_MODE" ;;
esac

if [[ "$SERVICE_MODE" == "always" ]]; then
  SERVICE_RESTART_BLOCK=$'Restart=always\nRestartSec=3'
  SERVICE_TYPE="simple"
else
  SERVICE_RESTART_BLOCK=$'Restart=no'
  SERVICE_TYPE="oneshot"
fi
if [[ "$SERVICE_MODE" == "interval" || "$SERVICE_MODE" == "daily" ]]; then
  if [[ -n "$WATCH_EXTRA_PATHS" && "$WATCH_EXTRA_PATHS" != "__NONE__" ]]; then
    warn "Watch paths are stored but ignored for timer-based jobs"
  fi
  HAS_WATCH_PATHS=false
fi

infer_hardening_mode

prompt_hardening_mode

HARDENING_BLOCK=""
[[ -n "$HARDEN_NO_NEW_PRIVS" ]]   && HARDENING_BLOCK+="NoNewPrivileges=$HARDEN_NO_NEW_PRIVS"$'\n'
[[ -n "$HARDEN_PRIVATE_TMP" ]]   && HARDENING_BLOCK+="PrivateTmp=$HARDEN_PRIVATE_TMP"$'\n'
[[ -n "$HARDEN_PROTECT_SYSTEM" ]]&& HARDENING_BLOCK+="ProtectSystem=$HARDEN_PROTECT_SYSTEM"$'\n'
[[ -n "$HARDEN_PROTECT_HOME" ]]  && HARDENING_BLOCK+="ProtectHome=$HARDEN_PROTECT_HOME"$'\n'

prompt_service_dependencies

# ============================================================
# Summary
# ============================================================
echo "----------------------------------------------------"
echo "Service creation plan"
echo "Job:        $JOB_NAME"
echo "Run as:     $RUN_AS_USER"
echo "Target:     $(target_script)"
echo "Mode:       $SERVICE_MODE"
echo "Watcher:    $([[ "$HAS_WATCH_PATHS" == true ]] && echo yes || echo no)"
echo "Schedule:   $(
  case "$SERVICE_MODE" in
    interval) echo "every ${INTERVAL_SECONDS}s" ;;
    daily)    echo "daily at ${DAILY_TIME}" ;;
    *)        echo "always running" ;;
  esac
)"
echo "Dependencies:"
[[ ${#AFTER_UNITS[@]} -gt 0 ]]    && echo "  After:    ${AFTER_UNITS[*]}"
[[ ${#WANTS_UNITS[@]} -gt 0 ]]    && echo "  Wants:    ${WANTS_UNITS[*]}"
[[ ${#REQUIRES_UNITS[@]} -gt 0 ]] && echo "  Requires: ${REQUIRES_UNITS[*]}"
[[ ${#AFTER_UNITS[@]} -eq 0 &&
   ${#WANTS_UNITS[@]} -eq 0 &&
   ${#REQUIRES_UNITS[@]} -eq 0 ]] && echo "  None"

echo -n "Hardening:  "

case "$HARDENING_MODE" in
  locked)
    echo "locked down"
    ;;
  none)
    echo "none"
    ;;
  custom)
    echo "custom (NoNewPrivs=$HARDEN_NO_NEW_PRIVS, PrivateTmp=$HARDEN_PRIVATE_TMP, ProtectSystem=$HARDEN_PROTECT_SYSTEM, ProtectHome=$HARDEN_PROTECT_HOME)"
    ;;
esac
echo "Dry run:    $([[ "$DRY_RUN" -eq 1 ]] && echo yes || echo no)"
echo "----------------------------------------------------"


confirm_or_exit
CONFIG_CHANGED=false
echo $WATCH_EXTRA_PATHS
[[ "$JOB_NAME" != "${ORIG_JOB_NAME:-}" ]] && CONFIG_CHANGED=true
[[ "$RUN_AS_USER" != "${ORIG_RUN_AS_USER:-}" ]] && CONFIG_CHANGED=true
[[ "$WATCH_EXTRA_PATHS" != "${ORIG_WATCH_EXTRA_PATHS:-}" ]] && CONFIG_CHANGED=true
[[ "$SERVICE_MODE" != "${ORIG_SERVICE_MODE:-}" ]] && CONFIG_CHANGED=true
[[ "$INTERVAL_SECONDS" != "${ORIG_INTERVAL_SECONDS:-}" ]] && CONFIG_CHANGED=true
[[ "$DAILY_TIME" != "${ORIG_DAILY_TIME:-}" ]] && CONFIG_CHANGED=true
[[ "$HARDEN_NO_NEW_PRIVS"   != "${ORIG_HARDEN_NO_NEW_PRIVS:-}"   ]] && CONFIG_CHANGED=true
[[ "$HARDEN_PRIVATE_TMP"   != "${ORIG_HARDEN_PRIVATE_TMP:-}"   ]] && CONFIG_CHANGED=true
[[ "$HARDEN_PROTECT_SYSTEM" != "${ORIG_HARDEN_PROTECT_SYSTEM:-}" ]] && CONFIG_CHANGED=true
[[ "$HARDEN_PROTECT_HOME"  != "${ORIG_HARDEN_PROTECT_HOME:-}"   ]] && CONFIG_CHANGED=true
[[ "$AFTER_SELECT_RAW" != "${ORIG_AFTER_SELECT_RAW:-}" ]] && CONFIG_CHANGED=true
[[ "$DEPS_SELECT_RAW"  != "${ORIG_DEPS_SELECT_RAW:-}"  ]] && CONFIG_CHANGED=true
[[ "$DEP_MODE_RAW"     != "${ORIG_DEP_MODE_RAW:-}"     ]] && CONFIG_CHANGED=true

if [[ -n "$CONFIG_FILE" ]]; then
  if [[ "$CONFIG_CHANGED" == true ]]; then
    prompt_save_config
  fi
else
  save_effective_config "$SAVE_CONFIG_PATH"
fi

# ============================================================
# Create target script
# ============================================================
run_cmd mkdir -p "$(target_dir)"
run_cmd chmod 755 "$(target_dir)"

TARGET_CONTENT=$(cat <<'EOF'
#!/usr/bin/env bash
#
# Script: start.sh
# Service: __JOB_NAME__
#

set -euo pipefail

custom_constants() { :; }
custom_variables() { :; }
validate_custom_variables() { :; }
service_execute() { :; }

source "/usr/services/lib/standard_service_main.sh"
main "$@"
EOF
)

write_file "$(target_script)" "${TARGET_CONTENT/__JOB_NAME__/$JOB_NAME}"
run_cmd chmod 755 "$(target_script)"

# ============================================================
# systemd service unit (AUTHORITATIVE)
# ============================================================
AFTER_BLOCK=""
WANTS_BLOCK=""
REQUIRES_BLOCK=""

SERVICE_UNIT_CONTENT=$(cat <<EOF
[Unit]
Description=${JOB_NAME}
__AFTER_BLOCK__
__WANTS_BLOCK__
__REQUIRES_BLOCK__

__BLANKLINE___
[Service]
Type=__SERVICE_TYPE__
User=root


__BLANKLINE___
ExecStart=/bin/bash \\
  ${WRAPPER_SERVICE_EXEC} \\
  --job=${JOB_NAME} \\
  --run-as=${RUN_AS_USER} \\
  --target=$(target_script)

__BLANKLINE___
ExecStop=/bin/bash \\
  ${WRAPPER_SERVICE_STOP} \\
  --job=${JOB_NAME}

__BLANKLINE___
__SERVICE_RESTART_BLOCK__
__HARDENING_BLOCK__

__BLANKLINE___
[Install]
WantedBy=multi-user.target
EOF
)

if [[ ${#AFTER_UNITS[@]} -gt 0 ]]; then
  AFTER_BLOCK="After=${AFTER_UNITS[*]}"
fi

if [[ ${#WANTS_UNITS[@]} -gt 0 ]]; then
  WANTS_BLOCK="Wants=${WANTS_UNITS[*]}"
fi

if [[ ${#REQUIRES_UNITS[@]} -gt 0 ]]; then
  REQUIRES_BLOCK="Requires=${REQUIRES_UNITS[*]}"
fi


UNIT="$SERVICE_UNIT_CONTENT"
UNIT="${UNIT/__AFTER_BLOCK__/$AFTER_BLOCK}"
UNIT="${UNIT/__WANTS_BLOCK__/$WANTS_BLOCK}"
UNIT="${UNIT/__REQUIRES_BLOCK__/$REQUIRES_BLOCK}"
UNIT="${UNIT/__SERVICE_RESTART_BLOCK__/$SERVICE_RESTART_BLOCK}"
UNIT="${UNIT/__SERVICE_TYPE__/$SERVICE_TYPE}"
UNIT="${UNIT/__HARDENING_BLOCK__/$HARDENING_BLOCK}"
UNIT="$(printf '%s\n' "$UNIT" | sed '/^[[:space:]]*$/d')"

UNIT="$(printf '%s\n' "$UNIT" | sed 's/^__BLANKLINE___$//')"



write_file "$SYSTEMD_DIR/${JOB_NAME}.service" "$UNIT"

# ============================================================
# systemd path unit (ONLY if watch paths exist)
# ============================================================
if [[ "$HAS_WATCH_PATHS" == true ]]; then
  PATH_UNIT_CONTENT=$(cat <<EOF
[Path]
PathModified=$(target_script)
PathChanged=$(target_script)
EOF
)
  write_file "$SYSTEMD_DIR/${JOB_NAME}.path" "$PATH_UNIT_CONTENT"

  IFS=';' read -r -a P <<< "$WATCH_EXTRA_PATHS"
  for p in "${P[@]}"; do
    append_file "$SYSTEMD_DIR/${JOB_NAME}.path" "PathModified=$p"
    append_file "$SYSTEMD_DIR/${JOB_NAME}.path" "PathChanged=$p"
  done

  append_file "$SYSTEMD_DIR/${JOB_NAME}.path" $'\n[Install]\nWantedBy=multi-user.target'
fi

if [[ "$SERVICE_MODE" == "interval" || "$SERVICE_MODE" == "daily" ]]; then
  TIMER_CONTENT="[Unit]
Description=${JOB_NAME} schedule

[Timer]
Persistent=true
"

  if [[ "$SERVICE_MODE" == "interval" ]]; then
    TIMER_CONTENT+="OnUnitActiveSec=${INTERVAL_SECONDS}
"
  else
    TIMER_CONTENT+="OnCalendar=*-*-* ${DAILY_TIME}:00
"
  fi

  TIMER_CONTENT+="
[Install]
WantedBy=timers.target
"

  write_file "$SYSTEMD_DIR/${JOB_NAME}.timer" "$TIMER_CONTENT"
  run_cmd systemctl enable "${JOB_NAME}.timer"
fi

# ============================================================
# Generate teardown helper (ephemeral)
# ============================================================
REMOVE_SCRIPT="/tmp/remove_${JOB_NAME}_service.sh"

REMOVE_SCRIPT_CONTENT=$(cat <<'EOF'
#!/usr/bin/env bash
#
# remove_service.sh
#
# Completely remove a service created by createlinuxservice_v2.sh
#

set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
SERVICES_DIR="/usr/services"

JOB_NAME="${1:-}"

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

info() {
  echo "[INFO]  $*"
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Must be run as root (use sudo)"
}

require_root

[[ -n "$JOB_NAME" ]] || die "Usage: sudo $0 <job-name>"

if [[ ! "$JOB_NAME" =~ ^[a-zA-Z0-9._@-]+$ ]]; then
  die "Invalid job name: '$JOB_NAME'"
fi

SERVICE_FILE="${SYSTEMD_DIR}/${JOB_NAME}.service"
PATH_FILE="${SYSTEMD_DIR}/${JOB_NAME}.path"
TIMER_FILE="${SYSTEMD_DIR}/${JOB_NAME}.timer"
TARGET_DIR="${SERVICES_DIR}/${JOB_NAME}"

echo "----------------------------------------------------"
echo "Service removal plan"
echo "Job name:      $JOB_NAME"
echo "----------------------------------------------------"
echo "Will remove (if present):"
echo "  - $SERVICE_FILE"
echo "  - $PATH_FILE"
echo "  - $TIMER_FILE"
echo "  - $TARGET_DIR"
echo "----------------------------------------------------"

read -r -p "Proceed with full removal? [y/N]: " confirm
[[ "${confirm,,}" == "y" || "${confirm,,}" == "yes" ]] || die "Aborted by user"

info "Stopping services (if running)…"
systemctl stop "${JOB_NAME}.service" 2>/dev/null || true
systemctl stop "${JOB_NAME}.path"    2>/dev/null || true
systemctl stop "${JOB_NAME}.timer"   2>/dev/null || true

info "Disabling services…"
systemctl disable "${JOB_NAME}.service" 2>/dev/null || true
systemctl disable "${JOB_NAME}.path"    2>/dev/null || true
systemctl disable "${JOB_NAME}.timer"   2>/dev/null || true

info "Removing systemd unit files…"
rm -f "$SERVICE_FILE" "$PATH_FILE" "$TIMER_FILE"

if [[ -d "$TARGET_DIR" ]]; then
  info "Removing service directory: $TARGET_DIR"
  rm -rf "$TARGET_DIR"
fi

info "Reloading systemd daemon…"
systemctl daemon-reload

echo "----------------------------------------------------"
echo "Service '$JOB_NAME' has been fully removed."
echo "----------------------------------------------------"
EOF
)

write_file "$REMOVE_SCRIPT" "$REMOVE_SCRIPT_CONTENT"
run_cmd chmod 755 "$REMOVE_SCRIPT"


# ============================================================
# Reload + enable
# ============================================================
run_cmd systemctl daemon-reload

if [[ "$SERVICE_MODE" == "interval" || "$SERVICE_MODE" == "daily" ]]; then
  # Timer-driven jobs: enable timer ONLY
  run_cmd systemctl enable "${JOB_NAME}.timer"
else
  # Always-running services
  if [[ "$HAS_WATCH_PATHS" == true ]]; then
    run_cmd systemctl enable "${JOB_NAME}.service" "${JOB_NAME}.path"
  else
    run_cmd systemctl enable "${JOB_NAME}.service"
  fi
fi


echo "Service created successfully."
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY-RUN] No changes applied."
else
  echo
  echo "----------------------------------------------------"
  echo "Post-run helper guide"
  echo "----------------------------------------------------"

  if [[ -n "$SAVED_CONFIG_ACTUAL" ]]; then
    echo
    echo "Re-run or modify this service using the saved config:"
    echo
    echo "  sudo $0 --config=\"$SAVED_CONFIG_ACTUAL\""
    echo
    echo "This will:"
    echo "  - reuse the same job name, run-as user, and watch paths"
    echo "  - reuse the same service run mode (always / interval / daily)"
    echo "  - recreate or update the systemd units deterministically"
  fi

  echo
  echo "Common follow-up commands:"
  echo
  echo "  # View service status"
  echo "  systemctl status ${JOB_NAME}.service"
  [[ "$SERVICE_MODE" == "interval" || "$SERVICE_MODE" == "daily" ]] && \
    echo "  systemctl status ${JOB_NAME}.timer"
  [[ "$HAS_WATCH_PATHS" == true ]] && \
    echo "  systemctl status ${JOB_NAME}.path"

  echo
  echo "  # View logs"
  echo "  journalctl -u ${JOB_NAME}.service -f"

  echo
  echo "  # Restart service manually"
  echo "  systemctl restart ${JOB_NAME}.service"

  if [[ "$SERVICE_MODE" == "interval" || "$SERVICE_MODE" == "daily" ]]; then
    echo
    echo "Timer notes:"
    if [[ "$SERVICE_MODE" == "interval" ]]; then
      echo "  - This service runs every ${INTERVAL_SECONDS} seconds"
      echo "  - Next run time can be checked with:"
      echo "      systemctl list-timers ${JOB_NAME}.timer"
    else
      echo "  - This service runs daily at ${DAILY_TIME}"
      echo "  - Next run time can be checked with:"
      echo "      systemctl list-timers ${JOB_NAME}.timer"
    fi
  fi

  echo
  echo "Target script location:"
  echo "  $(target_script)"

  echo
  echo "You may safely edit the target script to implement service logic."
  echo "Changes to the script do not require re-running this tool."
  echo
  echo
  echo "Service removal helper (optional):"
  echo "  Removes this service completely (units + files)."
  echo "  Run: sudo $REMOVE_SCRIPT $JOB_NAME"
  
  echo "----------------------------------------------------"
fi
