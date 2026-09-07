#!/usr/bin/env python3
"""Wait for the supervised runtime to serve its local status socket."""
import json
import sys
import time
from wledctl import LocalConnection

deadline = time.monotonic() + 10
while time.monotonic() < deadline:
    connection = LocalConnection('/run/fpp-wled/control.sock', timeout=1)
    try:
        connection.request('GET', '/api/status')
        response = connection.getresponse()
        data = json.loads(response.read())
        if response.status == 200 and data.get('release') == 'alpha.1':
            print('Runtime status endpoint healthy; FPP ownership may still be unavailable until FPP restarts.')
            sys.exit(0)
    except (OSError, ValueError):
        pass
    finally:
        connection.close()
    time.sleep(0.2)
sys.exit('Runtime did not become healthy within 10 seconds')
