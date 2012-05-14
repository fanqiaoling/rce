#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       ROSProcessor.py
#       
#       Copyright 2012 dominique hunziker <dominique.hunziker@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#       
#       

# twisted specific imports
from twisted.python import log

# Custom imports
from Exceptions import InvalidRequest, InternalError
from ProcessorBase import ProcessorBase
from TypeBase import MessageTypes as MsgTypes
from Base import Message

class ROSAddNode(ProcessorBase):
    """ Message processor to add a/multiple node(s).
    """
    IDENTIFIER = MsgTypes.ROS_ADD
    
    def processMessage(self, msg):
        for node in msg.content:
            try:
                self.manager.addNode(node)
            except InternalError as e:
                log.msg('Could not add Node: {0}'.format(e))

class ROSRemoveNode(ProcessorBase):
    """ Message processor to remove a/multiple node(s).
        
        Should be a list of ROSUtil.Node
    """
    IDENTIFIER = MsgTypes.ROS_REMOVE
    
    def processMessage(self, msg):
        for uid in msg.content:
            try:
                self.manager.removeNode(uid)
            except InvalidRequest as e:
                log.msg('Could not remove Node: {0}'.format(e))

class ROSMessageContainer(ProcessorBase):
    """ Message processor for a single ROS message in the container node.
    """
    IDENTIFIER = MsgTypes.ROS_MSG
    
    def processMessage(self, msg):
        rosMsg = msg.content['msg']
        interface = self.manager.getInterface(msg.content['name'])
        
        if msg.content['push']:
            try:
                interface.send(rosMsg, (msg.origin, msg.content['uid']))
            except InternalError as e:
                log.msg('Could not send ROS Message: {0}'.format(e))
        else:
            respMsg = Message()
            respMsg.msgType = MsgTypes.ROS_RESPONSE
            respMsg.dest = msg.origin
            
            try:
                respMsg.content = { 'msg' : interface.send(rosMsg), 'error' : False }
            except InternalError as e:
                log.msg('Could not send ROS Message: {0}'.format(e))
                respMsg.content = { 'msg' : str(e), 'error' : True }
            
            self.sendMessage(respMsg)

class ROSMessageMaster(ProcessorBase):
    """ Message processor for a single ROS message in the master node.
    """
    IDENTIFIER = MsgTypes.ROS_MSG
    
    def processMessage(self, msg):
        pass
        # TODO: Add logic to process message in master node

class ROSGet(ProcessorBase):
    """ Message processor for a single ROS message request.
    """
    IDENTIFIER = MsgTypes.ROS_GET
    
    def processMessage(self, msg):
        interface = self.manager.getInterface(msg.content['name'])
        
        respMsg = Message()
        respMsg.msgType = MsgTypes.ROS_MSG
        respMsg.dest = msg.origin
        
        try:
            respMsg.content = { 'msg' : interface.receive(msg.content['uid']),
                                'name' : '',
                                'uid' : '#TODO: What is a good value here?',
                                'push' : False }
        except InternalError as e:
            log.msg('Could not send ROS Message: {0}'.format(e))
        
        self.sendMessage(respMsg)