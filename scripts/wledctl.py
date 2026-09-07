#!/usr/bin/env python3
"""Local FPP/xSchedule hooks. A successful Show Start is required before playback."""
import argparse
import http.client
import json
import socket


class LocalConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.host)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('operation', choices=['show-start', 'show-end', 'ambient-enable', 'ambient-disable', 'status'])
    p.add_argument('source', nargs='?')
    p.add_argument('--socket', default='/run/fpp-wled/control.sock')
    args = p.parse_args()
    connection = LocalConnection(args.socket, timeout=5)
    connection.request('POST', '/api/command', json.dumps({'operation': args.operation, 'source': args.source}),
                       {'Content-Type': 'application/json'})
    response = connection.getresponse()
    print(response.read().decode())
    connection.close()
    raise SystemExit(0 if response.status == 200 else 1)


if __name__ == '__main__':
    main()
