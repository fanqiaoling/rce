#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       Protocol.py
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
from zope.interface import implements
from twisted.python import log
from twisted.internet.protocol import Protocol
from twisted.internet.interfaces import IPushProducer, IConsumer

# Custom imports
from Exceptions import InternalError
import Message.Definition as MsgDef
from Message.Base import DestinationError
from Message.Handler import MessageReceiver, Sink

class ReappengineProtocol(Protocol):
    """ Reappengine Protocol.

        To send a message using this protocol a push producer should be
        registered with this protocol. The direct usage of the transport
        object is no permitted.
    """
    implements(IPushProducer, IConsumer)

    def __init__(self, factory, addr):
        """ Instantiate the Reappengine Protocol.
            
            @param factory:     Factory which created this connection.
            @type  factory:     ReappengineFactory
            
            @param addr:        Address from where the connection originated.
            @type  addr:        ()    # TODO: Add specification
        """
        # Reference to parent for using persistent data
        self._factory = factory
        self._manager = factory.manager

        # Protocol variables
        self._addr = addr
        self.dest = None
        self.initialized = False
        self.paused = False
        
        # Variables to store current message
        self._recvBuf = ''
        self._currentMsgLength = -1
        self._msgDest = ''
        self._parsedBytes = 0
        
        # Reference on current producer
        self._producer = None
    
    def connectionMade(self):
        """ This method is called once the connection is established.
        """
        self._factory.startInit(self)
    
    def recievedInitMessage(self, msg):
        """ This method is called when a message is received, but the
            connection is not yet initialized.
        """
        self._factory.processInitMessage(msg, self)
    
    def dataReceived(self, data):
        """ Convert received raw data into appropriate messages.
        """
        # First add new data to existing buffer
        self._recvBuf += data

        # Run processing as long as there is no pause requested
        while not self.paused:
            # Calculate current length of buffer
            lenBuf = len(self._recvBuf)
            
            # If there is nothing to do return
            if not lenBuf:
                break

            # Next check if we are currently processing a message
            if self._currentMsgLength == -1:        # Indicates that there is no message
                # Check if there is enough data available to parse necessary part of the header
                if lenBuf > MsgDef.POS_DEST + MsgDef.ADDRESS_LENGTH:
                    # Parse header
                    self._currentMsgLength, = MsgDef.I_STRUCT.unpack(self._recvBuf[:MsgDef.I_LEN])
                    self._msgDest = self._recvBuf[MsgDef.POS_DEST:MsgDef.POS_DEST + MsgDef.ADDRESS_LENGTH]
                    msgType = self._recvBuf[MsgDef.POS_MSG_TYPE:MsgDef.POS_MSG_TYPE + MsgDef.MSG_TYPE_LENGTH]
                    
                    if self._currentMsgLength > MsgDef.MAX_LENGTH:
                        # TODO: What to do with message which is too long?
                        #       At the moment the data is read but not saved or parsed.
                        log.msg('Message is too long and will be dropped.'.format(msgType))
                        self._msgDest = Sink()
                    elif not self.initialized:
                        # Other side is not yet authenticated
                        self._msgDest = MessageReceiver(self._manager, False)
                    elif self._factory.filterMessage(msgType):
                        # Message should be filtered out
                        log.msg('Message of type "{0}" has been filtered out.'.format(msgType))
                        self._msgDest = Sink()
                    else:
                        # Everything ok; try to resolve destination
                        try:
                            self._msgDest = self._manager.nextDest(self._msgDest, self.dest)
                        except DestinationError:
                            # TODO: Resolve this DestinationError with specialized consumer/producer to process message.
                            #       At the moment the data is read but not saved or parsed.
                            self._msgDest = Sink()

                    # Register this instance as a producer with the retrieved consumer
                    self._msgDest.registerProducer(self, True)
                    continue    # Important: Start loop again to make sure that we are not on hold!
                else:
                    # Not enough data available return
                    break
            
            # Check if we have reached the end of a message in the buffer
            if lenBuf + self._parsedBytes >= self._currentMsgLength:
                # We have reached the end
                self._msgDest.write(self._recvBuf[:self._currentMsgLength - self._parsedBytes])
                self._msgDest.unregisterProducer()
                self._recvBuf = self._recvBuf[self._currentMsgLength - self._parsedBytes:]

                # Reset message specific variables
                self._currentMsgLength = -1
                self._msgDest = ''
                self._parsedBytes = 0
            else:
                # We haven't reached the end of the message yet
                self._msgDest.write(self._recvBuf)
                self._recvBuf = ''

                # Update number of parsed bytes
                self._parsedBytes += lenBuf

    def requestSend(self):
        """ Request that this protocol instance sends a message.
        """
        if not self._producer and self.initialized and self.dest and self._manager.producerQueue[self.dest]:
            self._manager.producerQueue[self.dest].pop(0)[0].send(self)

    def registerProducer(self, producer, streaming):
        """ Register a producer which be used to send a message. The
            producer should be a push producer, i.e. streaming should
            be true. If this is not the case an exception is raised.

            Important:
                The producers should not use this method without being
                asked to do so, i.e. the protocol will call 'send' as soon
                as it is ready to receive a new message.
                Instead the producer should add himself to the producerQueue
                of the manager.
        """
        if not streaming:
            raise NotImplementedError('Pull Producer are not supported; use Push Producer instead.')

        if self._producer:
            raise InternalError('Tried to register a producer without unregister previous producer.')

        self._producer = producer
        self.transport.registerProducer(producer, True)

    def write(self, data):
        """ Method which is used by the producer to send data of this
            protocol instance.

            Important:
                Before the producer starts to write data he should do a
                check whether he can start producing or not!
        """
        self.transport.write(data)

    def unregisterProducer(self):
        """ Method which is used by the producer to signal that he has
            finished sending data.
        """
        self.transport.unregisterProducer()
        self._producer = None
        self.requestSend()

    def pauseProducing(self):
        """ Method for the consumer to signal that he can't accept (more)
            data at the moment.
        """
        self.paused = True
        self.transport.pauseProducing()

    def resumeProducing(self):
        """ Method for the consumer to signal that he can accept (again)
            data.
        """
        self.paused = False
        self.transport.resumeProducing()
        self.dataReceived('')

    def stopProducing(self):
        """ Method for the consumer to signal that the producer should
            stop sending data.
        """
        # TODO: Drop the current message; how could this be achieved ?!?
        #       Or in other words how can we figure out where the new message start in the buffer
        #       when not the full length of the previous message is received...
        self.paused = True
        self.transport.stopProducing()

    def connectionLost(self, reason):
        """ Method which is called when the connection is lost.
        """
        # First of all remove the connection from the factory/manager
        self._factory.unregisterConnection(self)
        # TODO: Is anything else necessary?
        
        reason.printTraceback(detail='verbose')
