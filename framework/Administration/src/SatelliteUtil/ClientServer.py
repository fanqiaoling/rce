#!/usr/bin/env python
from twisted.internet import reactor
from autobahn.websocket import WebSocketServerFactory, WebSocketServerProtocol, listenWS

import json
import uuid
from Queue import Queue

from ROSProxy import ROSProxy

from Robot import Robot

class WebSocketCloudEngineProtocol(WebSocketServerProtocol):
    
    incoming_msg_count = 0 
    cmd_CSR = {"type":"CSR", "dest":None, "orig":"$$$$$$", "data":{"containerID":None}}
    
    def __init__(self, manager):
        self._manager = manager
        self._robot = None
    
    def onConnect(self, _):
        pass
    
    def connectionMade(self):
        self.connectionManager = connectionManager(self)
    
    def onMessage(self, msg, binary):
        if not self.initialized:
            # Initialize
            self._robot = Robot("RobotID", self, self._manager)
        else:            
            # Debug 
            self.incoming_msg_count += 1
            print('received Message # '+str(self.incoming_msg_count))

            if not binary:
                cmd = json.loads(msg)
                if cmd['type']=="CS":
                    print "received container creation method"
                    self.cmd_CSR['dest']=cmd['orig']
                    self.cmd_CSR['data']['containerID']=uuid.uuid4().hex
                    self.sendMessage(json.dumps(self.cmd_CSR))
                else:
                    self.sendMessage('received Message # '+str(self.incoming_msg_count))
            else:
                pass
    
    def connectionLost(self, reason):
        self._robot = None

class WebSocketCloudEngineFactory(WebSocketServerFactory):
    def __init__(self, manager, url):
        WebSocketServerFactory.__init__(self, url)
        
        self.manager = manager
    
    def buildProtocol(self, addr):
        protocol = WebSocketCloudEngineProtocol(self.manager)
        protocol.factory = self
        return protocol
