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
import json

from Queue import Queue
from logger import *

class Service_Thread_TCP(threading.Thread):
    """
    Title: RF Front End Daemon, Service Thread
    Project: VTGS RF Front End Daemon
    Version: 1.0
    Date: June 2019
    Author: Zach Leffke, KJ4QLP

    Purpose:
        Handles RFFE Service interface to GNU Radio

    Args:
        cfg - Configurations for thread, dictionary format.
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

        self.data_logger = None

    def run(self):
        self.logger.info('Launched {:s}'.format(self.name))
        self._init_socket()
        while (not self._stop.isSet()):
            if not self.connected:
                try:
                    self._attempt_connect()
                except socket.error, e:
                    if e.errno == errno.ECONNREFUSED:
                        self.connected = False
                        time.sleep(self.cfg['retry_time'])
                except Exception as e:
                    self._handle_socket_exception(e)
            else:
                try:
                    data = self.sock.recvfrom(1024)
                    if not data[0]:
                        self.logger.info("Disconnected from {:s}: [{:s}:{:d}]".format(self.cfg['name'],
                                                                                      self.cfg['ip'],
                                                                                      self.cfg['port']))
                        self._reset_socket()
                    else:
                        self._handle_recv_data(data[0])
                except socket.timeout, e: #Expected after connection
                    self._handle_socket_timeout()
                except Exception as e:
                    self._handle_socket_exception(e)
            time.sleep(0.000001)

        self.sock.close()
        self.logger.warning('{:s} Terminated'.format(self.name))
        #sys.exit()

    def _start_logging(self):
        self.cfg['log']['startup_ts'] = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        setup_logger(self.cfg['log'])
        self.data_logger = logging.getLogger(self.cfg['log']['name']) #main logger
        for handler in self.data_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                self.logger.info("Started {:s} Data Logger: {:s}".format(self.name, handler.baseFilename))

    def _stop_logging(self):
        if self.data_logger != None:
            handlers = self.data_logger.handlers[:]
            print handlers
            for handler in handlers:
                if isinstance(handler, logging.FileHandler):
                    self.logger.info("Stopped Logging: {:s}".format(handler.baseFilename))
                handler.close()
                self.data_logger.removeHandler(handler)
            self.data_logger = None

    #### Socket and Connection Handlers ###########
    def _handle_recv_data(self, data):
        try:
            json_data = json.loads(data.strip())
            self.logger.info("Received Valid JSON PTT: {:s}".format(data.strip()))
            if self.data_logger != None:
                self.data_logger.info(json_data)
            #DO MORE VALIDATION HERE
            self.rx_q.put(json_data)
            #ECHO PTT Back to Flowgraph
            #May change to send PA TM to FG for display
            self.tx_q.put(json.dumps(json_data)) #ECHO PTT Back to Flowgraph
        except Exception as e:
            self.logger.info("Received Invalid JSON PTT: {:s}".format(data.strip()))

    def _handle_socket_timeout(self):
        if self.connected:
            if not self.tx_q.empty():
                tx_msg = self.tx_q.get()
                self.sock.sendall(tx_msg)

    def _attempt_connect(self):
        self.sock.connect((self.cfg['ip'], self.cfg['port']))
        self.logger.info("Connected to {:s}: [{:s}, {:d}]".format(self.cfg['name'],
                                                                   self.cfg['ip'],
                                                                   self.cfg['port']))

        time.sleep(0.01)
        self.sock.settimeout(self.cfg['timeout'])   #set socket timeout
        self.connected = True
        self.parent.set_service_con_status(self.connected)
        self._start_logging()


    def _handle_socket_exception(self, e):
        self.logger.debug("Unhandled Socket error")
        self.logger.debug(sys.exc_info())
        self._reset_socket()

    def _reset_socket(self):
        self.logger.debug('resetting socket...')
        self.sock.close()
        self.connected = False
        self.parent.set_service_con_status(self.connected)
        self._stop_logging()
        self._init_socket()

    def _init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP Socket, initialize
        self.logger.debug("Setup socket")
        self.logger.info("Attempting to connect to {:s}: [{:s}, {:d}]".format(self.cfg['name'],
                                                                               self.cfg['ip'],
                                                                               self.cfg['port']))
    #### END Socket and Connection Handlers ###########


    def stop(self):
        #self.conn.close()
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
