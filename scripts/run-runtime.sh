#!/bin/bash
set -eo pipefail
. "$(dirname "$0")/fpp-paths.sh"
# Both Python and native renderer diagnostics share the FPP-managed log.
exec >>"$PLUGIN_LOG" 2>&1
cd "${PLUGINDIR}/${PLUGIN_NAME}/build/current"
exec python3 -u -m runtime.service --state-dir "$PLUGIN_STATE"
