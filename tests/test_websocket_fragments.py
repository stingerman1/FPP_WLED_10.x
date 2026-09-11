import base64
import json
import socket
import struct
import unittest
import test_runtime
from runtime.web import start_servers

class FragmentTests(unittest.TestCase):
    setUp=test_runtime.RuntimeTests.setUp
    enable=test_runtime.RuntimeTests.enable
    idle=test_runtime.RuntimeTests.idle

    def connect(self,authenticated=True):
        self.enable();self.control.config['port']=0
        run=self.directory/'ws';run.mkdir()
        servers=start_servers(self.control,run,self.directory)
        def close():
            for server in servers:server.stop_event.set();server.shutdown();server.server_close()
        self.addCleanup(close)
        sock=socket.create_connection(('127.0.0.1',servers[0].server_address[1]));sock.settimeout(3);self.addCleanup(sock.close)
        token=servers[0].token
        headers='Authorization: Bearer '+token+'\r\n' if authenticated else ''
        sock.sendall(('GET /ws HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'+headers+'\r\n').encode())
        stream=sock.makefile('rb');self.addCleanup(stream.close)
        self.assertIn(b'101',stream.readline())
        while stream.readline()!=b'\r\n':pass
        self.read(stream) # initial state
        return sock,stream

    def read(self,stream):
        header=stream.read(2);self.assertEqual(len(header),2)
        length=header[1]&127
        if length==126:length=struct.unpack('!H',stream.read(2))[0]
        elif length==127:length=struct.unpack('!Q',stream.read(8))[0]
        return header[0]&15,stream.read(length)

    def send(self,sock,opcode,body,final=True):
        mask=b'abcd';size=len(body);header=bytes([(128 if final else 0)|opcode])
        header+=bytes([128|size]) if size<126 else bytes([128|126])+struct.pack('!H',size)
        sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(body)))

    def test_fragmented_command_with_ping(self):
        sock,stream=self.connect()
        self.send(sock,1,b'{"bri":',False);self.send(sock,9,b'ping')
        self.assertEqual(self.read(stream),(10,b'ping'))
        self.assertNotEqual(self.control.state.value['bri'],71)
        self.send(sock,0,b'71}')
        opcode,body=self.read(stream)
        self.assertEqual(opcode,1);self.assertEqual(json.loads(body)['state']['bri'],71)

    def test_fragmentation_does_not_bypass_auth(self):
        sock,stream=self.connect(False)
        self.send(sock,1,b'{"bri":',False);self.send(sock,0,b'71}')
        self.assertIn('error',json.loads(self.read(stream)[1]))
        self.assertNotEqual(self.control.state.value['bri'],71)

    def test_orphan_continuation_rejected(self):
        sock,stream=self.connect();self.send(sock,0,b'{}')
        self.assertEqual(self.read(stream),(8,struct.pack('!H',1002)))
