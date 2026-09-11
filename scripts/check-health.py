#!/usr/bin/env python3
"""Wait for the supervised runtime to serve its local status socket."""
import json
import sys
import time
from wledctl import LocalConnection

def healthy(status, data):
    # The local socket identifies the runtime. Release labels are not protocol
    # versions: both upgrades and rollbacks must pass this readiness check.
    return (status == 200 and isinstance(data, dict) and data.get('version') == 1
            and isinstance(data.get('release'), str) and bool(data['release'])
            and type(data.get('observer_healthy')) is bool)


def main():
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        connection = LocalConnection('/run/fpp-wled/control.sock', timeout=1)
        try:
            connection.request('GET', '/api/status')
            response = connection.getresponse()
            data = json.loads(response.read())
            if healthy(response.status, data):
                print('Runtime status endpoint healthy; FPP ownership may still be unavailable until FPP restarts.')
                return
        except (OSError, ValueError):
            pass
        finally:
            connection.close()
        time.sleep(0.2)
    sys.exit('Runtime did not become healthy within 10 seconds')


if __name__ == '__main__':
    main()
