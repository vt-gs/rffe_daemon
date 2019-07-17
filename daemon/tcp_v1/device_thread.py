#!/usr/bin/env python
################################################################################
#   Title: RF Front End Control Daemon Device Thread
# Project: VTGS
# Version: 1.0.0
#    Date: Aug 26, 2018
#  Author: Zach Leffke, KJ4QLP
# Comments:
#   -This is the RF Front End Device thread
################################################################################

import threading
import time
import socket
import errno
import json

from Queue import Queue
from logger import *
from power_amp import *

class VHF_UHF_PA_Thread(threading.Thread):
    """
    Title: RF Front End Daemon, Device Thread
    Project: VTGS RF Front End Daemon
    Version: 1.0
    Date: June 2019
    Author: Zach Leffke, KJ4QLP

    Purpose:
        Handles PA Service interface to GNU Radio

    Args:
        cfg - Configurations for thread, dictionary format.
        parent - parent thread, used for callbacks

    """
    def __init__ (self, cfg, parent=None):
        threading.Thread.__init__(self)
        self._stop  = threading.Event()
        self.cfg    = cfg
        self.parent = parent
        self.setName(self.cfg['thread_name'])
        self.logger = logging.getLogger(self.cfg['main_log'])

        self.rx_q   = Queue() #MEssages received from client, command
        self.tx_q   = Queue() #Messages sent to client, feedback

        self.amp = VHF_UHF_Power_Amplifier(self.cfg, self)

        self.connected = False
        self.logger.info("Initializing {}".format(self.name))

        self.data_logger = None

    def run(self):
        self.logger.info('Launched {:s}'.format(self.name))
        #self._init_socket()
        while (not self._stop.isSet()):
            if (not self.connected): #attempt to connect
                self._attempt_connect()
            elif self.connected:
                if not self.tx_q.empty():
                    msg = self.tx_q.get()
                    if   msg == 'TX':
                        self._set_amp_tx('UHF')
                        #self._query_amp()
                    elif msg == 'RX':
                        self._set_amp_rx()
                        #self._query_amp()
                self._query_amp()
        #self.sock.close()
        self.logger.warning('{:s} Terminated'.format(self.name))
        #sys.exit()


    def _query_amp(self):
        tm = self.amp.get_telemetry()
        self.data_logger.info(json.dumps(tm))
        self.rx_q.put(json.dumps(tm))
        #print json.dumps(tm, indent=4)

    def _set_amp_tx(self, mode):
        self.amp.set_tx_mode(mode)
        self.logger.info('sent TX: {:s}'.format(mode))

    def _set_amp_rx(self):
        self.amp.set_rx_mode()
        self.logger.info('sent RX')



    def _attempt_connect(self):
        self.connected = self.amp.connect()
        if self.connected:
            self.logger.info("Connected to {:s}: [{:s}, {:d}]".format( self.cfg['name'],
                                                                       self.cfg['ip'],
                                                                       self.cfg['port'] ))
            self.parent.set_device_con_status(self.connected)
            self._start_logging()
        else:
            time.sleep(self.cfg['retry_time'])





    #### Logging ###########
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
    #### Logging ###########



    def stop(self):
        #self.conn.close()
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


    ##################  OLD FUNCTIONS BELOW ##########################











    def _handle_recv_data(self, data):
        if data.strip() == self.tc_msg:
            data = self.sock.recvfrom(1024)
            print data
        else:
            self.logger.info("Disconnected from {:s}: [{:s}:{:d}]".format(self.cfg['name'],
                                                                          self.cfg['ip'],
                                                                          self.cfg['port']))
            self._reset_socket()

    def _handle_recv_data_old(self, data):
        print data



        try:

            json_data = json.loads(data.strip())
            #self.logger.info("Received Valid JSON PTT: {:s}".format(data.strip()))
            if self.data_logger != None: self.data_logger.info(json_data)
            #print json.dumps(json.loads(data.strip()), indent=4)
            #DO MORE VALIDATION HERE
            #self.parent.ptt_received(json_data)
            self.rx_q.put(json_data)
            #ECHO PTT Back to Flowgraph
            #May change to send PA TM to FG for display
        except Exception as e:
            self.logger.info("Received Invalid JSON PTT: {:s}".format(data.strip()))



    #### Socket and Connection Handlers ###########
    def _handle_socket_timeout(self):
        if self.connected:
            if not self.tx_q.empty():
                pa_msg = self.tx_q.get()
                if   pa_msg == 'TX': self._send_amp_tc('uhf_tx')
                elif pa_msg == 'RX': self._send_amp_tc('rx_all')
                #self.sock.sendall(tx_msg)



    def _handle_socket_exception(self, e):
        self.logger.debug("Unhandled Socket error")
        self.logger.debug(sys.exc_info())
        self._reset_socket()

    def _reset_socket(self):
        self.logger.debug('resetting socket...')
        self.sock.close()
        self.connected = False
        self.parent.set_device_con_status(self.connected)
        self._stop_logging()
        self._init_socket()

    def _init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP Socket, initialize
        self.logger.debug("Setup socket")
        self.logger.info("Attempting to connect to {:s}: [{:s}, {:d}]".format(self.cfg['name'],
                                                                               self.cfg['ip'],
                                                                               self.cfg['port']))
    #### END Socket and Connection Handlers ###########
