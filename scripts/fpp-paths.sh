#!/bin/bash
# FPP owns path resolution, including relocated media directories.
: "${FPPDIR:=/opt/fpp}"
set +u
. "${FPPDIR}/scripts/common"
PLUGIN_NAME=FPP_WLED_10.x
PLUGIN_STATE="${MEDIADIR}/plugindata/${PLUGIN_NAME}"
PLUGIN_LOG="${LOGDIR}/plugin-${PLUGIN_NAME}.log"
export MEDIADIR LOGDIR PLUGIN_STATE PLUGIN_LOG
