#!/usr/bin/env python
#############################################
#   Title: Numato Ethernet Relay Interface  #
# Project: VTGS Relay Control Daemon        #
# Version: 2.0                              #
#    Date: Dec 15, 2017                     #
#  Author: Zach Leffke, KJ4QLP              #
# Comment:                                  #
#   -Relay Control Daemon                   #
#   -Intended for use with systemd          #
#############################################

import sys
import threading
import logging
import time
import binascii

from Queue import Queue

class VHF_UHF_PA_Thread(threading.Thread):
    def __init__ (self, cfg, logger, parent=None):
        threading.Thread.__init__(self, name = None)
        self._stop  = threading.Event()
        self.cfg    = cfg
        self.logger = logger
        self.parent = parent
        self.name   = self.cfg['name'].upper()+"_Thread"

        print "Initializing {}".format(self.name)
        self.logger.info("Initializing {}".format(self.name))


        self.ssid   = self.cfg['ssid']
        self.delay  = self.cfg['delay']

        self.device = VHF_UHF_Power_Amplifier(cfg, logger, self)

        self.tx_q       = Queue() #messages into thread
        self.rx_q       = Queue() #messages from thread
        self.timer = threading.Timer(self.timeout, self._timer_handler)

        self.connected  = False

    def run(self):
        print "{:s} Started...".format(self.name)
        self.logger.info('Launched {:s}'.format(self.name))
        if (not self.connected):
            self.connect()
        while (not self._stop.isSet()):
            if self.connected:
                if (not self.tx_q.empty()): #Message for RFFE Received
                    msg = self.tx_q.get()
                    print '{:s} | {:s}'.format(self.name, msg)
                    self._process_cmd(msg)

            else:
                time.sleep(5)
                self.connect()

            time.sleep(0.01) #Needed to throttle CPU

        self.logger.warning('{:s} Terminated'.format(self.name))
        sys.exit()

    def _timer_handler(self):
        print 'RFFE Timeout, setting to RX Mode....'
        self.resp = "RX_ALL_READY_TIMEOUT"
        self.rx_q.put(self.resp)


    def _process_cmd(self,msg):
        if msg == 'RX_REQ':
            self.resp = 'RX_ALL_READY'
            try:
                self.timer.cancel()
            except:
                pass
        elif ((msg =='TX_UHF_REQ') or (msg =='TX_VHF_REQ')):
            self.timer = threading.Timer(self.timeout, self._timer_handler)
            self.timer.start()
            self.resp = msg.replace('REQ', 'READY')
        else:
            self.resp = None

        if self.resp:
            time.sleep(0.01)#Simulated delay to interact with relay bank
            self.rx_q.put(self.resp)


    def connect(self):
        self.connected = True
        #Expand to connect to PA device
        # try:
        #     self.logger.info('Attempting to telnet to relay bank: {:s}'.format(self.ip))
        #     self.tn = telnetlib.Telnet(self.ip)
        #     self.tn.read_until("User Name: ")
        #     self.tn.write(self.username + "\n")
        #     #print 'entered login'
        #     if self.password:
        #         self.tn.read_until("Password: ")
        #         self.tn.write(self.password + "\n")
        #     resp = self.tn.read_until('>>')
        #     #print resp
        #     self.logger.info('Succesful telnet to relay bank: {:s}'.format(self.ip))
        #     self.connected = True
        #     print 'Connected!'
        # except:
        #     self.logger.info('Failed to telnet to relay bank: {:s}'.format(self.ip))
        #     self.connected = False

    def stop(self):
        print '{:s} Terminating...'.format(self.name)
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
