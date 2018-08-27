#!/usr/bin/env python
#############################################
#   Title: Relay Daemon Service Thread      #
# Project: VTGS Relay Control Daemon        #
# Version: 2.0                              #
#    Date: Dec 15, 2017                     #
#  Author: Zach Leffke, KJ4QLP              #
# Comment:                                  #
#   -Relay Control Daemon Service Thread    #
#   -This is the User interface             #
#############################################

import threading
import time
import socket
import errno
import pika

from Queue import Queue
from logger import *
from rabbitcomms import BrokerConsumer
from rabbitcomms import BrokerProducer

class Consumer(BrokerConsumer):
    def __init__(self, cfg, loggername=None):
        super(Consumer, self).__init__(cfg, loggername)
        self.q  = Queue() #place received messages here.

    def process_message(self, method, properties, body):
        msg = 'Received message {:s} from {:s} {:s}'.format(str(method.delivery_tag), str(properties.app_id), str(body))
        self.q.put(msg)

    def get_connection_state(self):
        return self.connected

class Producer(BrokerProducer):
    def __init__(self, cfg, loggername=None):
        super(Producer, self).__init__(cfg, loggername)

    def get_connection_state(self):
        return self.connected


class Service_Thread_TCP(threading.Thread):
    def __init__ (self, ssid, cfg):
        threading.Thread.__init__(self, name = 'Service_Thread')
        self._stop  = threading.Event()
        self.ssid   = ssid
        self.cfg    = cfg

        self.rx_q   = Queue() #MEssages received from client, command
        self.tx_q   = Queue() #Messages sent to client, feedback

        self.connected = False

        self.logger = logging.getLogger(self.ssid)
        print "Initializing {}".format(self.name)
        self.logger.info("Initializing {}".format(self.name))

    def run(self):
        print "{:s} Launched...".format(self.name)
        self.logger.info('Launched {:s}'.format(self.name))

        while (not self._stop.isSet()):
            self.logger.info("Setting up socket...")
            print "{:s} Setting up socket...".format(self.name)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #self.sock.setblocking(0)
            #self.sock.settimeout(1)
            self.sock.bind((self.cfg['ip'], self.cfg['port']))
            self.sock.listen(1) #blocking until client connects
            self.logger.info("Server listening on: [{:s}:{:d}]".format(self.cfg['ip'], self.cfg['port']))
            print "Server listening on: [{:s}:{:d}]".format(self.cfg['ip'], self.cfg['port'])

            self.conn, self.client = self.sock.accept()
            self.logger.info("Connection from client: [{:s}:{:d}]".format(self.client[0], self.client[1]))
            print "Connection from client: [{:s}:{:d}]".format(self.client[0], self.client[1])
            self.connected = True
            while self.connected:
                self.conn.setblocking(0)
                self.conn.settimeout(.01)
                try:
                    data = self.conn.recv(1024).strip() # blocking until data
                    if data:
                        #print 'received', data
                        self.rx_q.put(data)


                    else: #client disconnects
                        self.connected = False
                except socket.error, v:
                    errorcode=v[0]
                    if errorcode =='timed out':
                        pass
                try:
                    if (not self.tx_q.empty()): #msg received for client
                        msg = self.tx_q.get()
                        print 'Sending Message to client: {:s}'.format(msg)
                        self.conn.sendall(msg)
                except socket.error, v:
                    self.connected = False


                time.sleep(.1)
            # except socket.error, v:
            #     errorcode=v[0]
            #     if errorcode==errno.EPIPE:  #Client disconnected
            #         print 'Client Disconnected'
            #         self.connected = False
            #         self.conn.close()
            #     #print errorcode
            # except Exception as e:
            #     print e
            #     self.conn.close()
            #     self.connected = False
            # time.sleep(0.01)#needed to throttle

        time.sleep(1)
        self.conn.close()
        self.logger.warning('{:s} Terminated'.format(self.name))
        #sys.exit()

    def get_connection_state(self):
        return self.connected

    def stop(self):
        print '{:s} Terminating...'.format(self.name)
        #self.conn.close()
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class Service_Thread_RMQ(threading.Thread):
    def __init__ (self, ssid, cfg):
        threading.Thread.__init__(self, name = 'Service_Thread')
        self._stop  = threading.Event()
        self.ssid   = ssid
        self.cfg    = cfg

        self.rx_q   = Queue() #MEssages received from Broker, command
        self.tx_q   = Queue() #Messages sent to broker, feedback

        self.consumer = Consumer(cfg, loggername=self.ssid)
        self.consume_thread = threading.Thread(target=self.consumer.run, name = 'Serv_Consumer')
        self.consume_thread.daemon = True

        self.producer = Producer(cfg, loggername=self.ssid)
        self.produce_thread = threading.Thread(target=self.producer.run, name = 'Serv_Producer')
        self.produce_thread.daemon = True

        self.connected = False

        self.logger = logging.getLogger(self.ssid)
        print "Initializing {}".format(self.name)
        self.logger.info("Initializing {}".format(self.name))

    def run(self):
        print "{:s} Started...".format(self.name)
        self.logger.info('Launched {:s}'.format(self.name))

        #Start consumer
        self.consume_thread.start()
        #star producer
        self.produce_thread.start()

        while (not self._stop.isSet()):
            if (self.consumer.get_connection_state() and self.producer.get_connection_state()):
                self.connected = True
            else:
                self.connected = False

            print self.connected

            if self.connected:
                if (not self.consumer.q.empty()): #received a message on command q
                    rx_msg = self.consumer.q.get()
                    self.rx_q.put(rx_msg)
                elif (not self.tx_q.empty()):#essage to send
                    tx_msg = self.tx_q.get()
                    self.producer.send(tx_msg)

            time.sleep(0.01)#needed to throttle

        self.consumer.stop_consuming()
        self.producer.stop_producing()
        time.sleep(1)
        self.consumer.stop()
        self.producer.stop()
        self.logger.warning('{:s} Terminated'.format(self.name))
        sys.exit()

    def get_connection_state(self):
        return self.connected

    def stop(self):
        print '{:s} Terminating...'.format(self.name)
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
