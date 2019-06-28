#!/usr/bin/env python
################################################################################
#   Title: RF Front End Control Daemon Service Thread
# Project: VTGS
# Version: 1.0.0
#    Date: Aug 26, 2018
#  Author: Zach Leffke, KJ4QLP
# Comments:
#   -This is the user interface thread
################################################################################

import threading
import time
import socket
import errno
import pika

from Queue import Queue
from logger import *

class Service_Thread_TCP(threading.Thread):
    """
    Title: RF Front End Daemon, Service Thread
    Project: VTGS Tracking Daemon
    Version: 1.0
    Date: June 2019
    Author: Zach Leffke, KJ4QLP

    Purpose:
        Handles PA Service interface to GNU Radio

    Args:
        cfg - Configurations for thread, dictionary format.
        logger - Logger passed from main thread.
        parent - parent thread, used for callbacks

    """
    def __init__ (self, cfg, parent):
        threading.Thread.__init__(self)
        self._stop  = threading.Event()
        self.cfg    = cfg
        self.parent = parent
        self.setName(self.cfg['thread_name'])
        self.logger = logging.getLogger(self.cfg['main_log'])

        self.rx_q   = Queue() #MEssages received from client, command
        self.tx_q   = Queue() #Messages sent to client, feedback

        self.connected = False

        self.logger.info("Initializing {}".format(self.name))

    def run(self):
        self.logger.info('Launched {:s}'.format(self.name))

        while (not self._stop.isSet()):
            self.logger.info("Setting up socket...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #self.sock.setblocking(0)
            #self.sock.settimeout(1)
            self.sock.bind((self.cfg['ip'], self.cfg['port']))
            self.sock.listen(1) #blocking until client connects
            self.logger.info("Server listening on: [{:s}:{:d}]".format(self.cfg['ip'], self.cfg['port']))

            self.conn, self.client = self.sock.accept()
            self.logger.info("Connection from client: [{:s}:{:d}]".format(self.client[0], self.client[1]))
            self.connected = True
            while self.connected:
                self.conn.setblocking(0)
                self.conn.settimeout(.001)
                try:
                    if (not self.tx_q.empty()): #msg received for client
                        msg = self.tx_q.get()
                        print 'Sending Message to client: {:s}'.format(msg)
                        self.conn.sendall(msg)
                except socket.error, v:
                    self.connected = False

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

                time.sleep(.1)

        time.sleep(1)
        self.conn.close()
        self.logger.warning('{:s} Terminated'.format(self.name))
        #sys.exit()

    def get_connection_state(self):
        return self.connected

    def stop(self):
        #self.conn.close()
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
