#!/usr/bin/env bash
# PID 1 for the release image, which runs two processes: the API and the
# Next.js server. Docker restarts a container, not a process inside one, so the
# only honest thing to do when either half dies is to take the whole container
# down with it. Without that you get the failure this script exists to prevent:
# a container that is still "up", still passing a port check, and answering
# nothing on half its surface.
#
# Compose runs the two as separate services and needs none of this. See
# openwiki/decisions/2026-09-05-the-release-image-is-one-container.md.
set -uo pipefail

api_pid=""
web_pid=""

# Set by the trap, read after each launch. A `docker stop` in the first
# milliseconds can land between starting a process and recording its pid, and
# a handler that only kills what it knows about would kill nothing and let the
# script go on starting the rest - a container that ignores its stop until
# Docker loses patience and sends SIGKILL ten seconds later.
shutting_down=""

stop() {
    # Disarmed first, so a second signal - or the trap firing again while the
    # kill below is still going - cannot re-enter this.
    trap - TERM INT
    shutting_down=1
    # Unquoted and defaulted: a pid that has not been recorded yet disappears
    # from the command line rather than becoming an empty argument. Redirected
    # because a process that has already exited makes kill complain about a pid
    # that is gone, on a path where that is the expected case.
    kill -TERM ${api_pid:-} ${web_pid:-} 2>/dev/null || true
}

trap stop TERM INT

# 128 + SIGTERM, the exit status a process killed by that signal reports.
readonly TERMINATED=143

# The venv's own uvicorn rather than `uv run`: the process is unprivileged and
# has no home directory, and uv wants a cache directory it cannot write. The
# command line is otherwise the one in backend/Dockerfile - --limit-concurrency
# bounds requests in flight, which the 50MB per-request ceiling does not.
/app/.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 --limit-concurrency 8 &
api_pid=$!

# After the assignment, not before it: this is the window the flag exists for.
if [[ -n "${shutting_down}" ]]; then
    kill -TERM "${api_pid}" 2>/dev/null || true
    wait 2>/dev/null
    exit "${TERMINATED}"
fi

# A subshell, because the interface has to be started from its own directory:
# the standalone server resolves .next/static and public relative to the
# working directory, and the API is loaded as `app.main` relative to /app.
(cd /app/web && exec node server.js) &
web_pid=$!

if [[ -n "${shutting_down}" ]]; then
    stop
    wait 2>/dev/null
    exit "${TERMINATED}"
fi

# Whichever exits first, for whatever reason, ends the container.
wait -n
status=$?

stop
wait 2>/dev/null

exit "${status}"
