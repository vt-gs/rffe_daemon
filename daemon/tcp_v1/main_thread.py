#!/usr/bin/env python
################################################################################
#   Title: RF Front End Control Daemon Main Thread
# Project: VTGS
# Version: 1.0.0
#    Date: Aug 26, 2018
#  Author: Zach Leffke, KJ4QLP
# Comments:
#   -RF Front End Control Daemon
#   -Intended for use with systemd
#   -Starting with TCP, but intend to add RMQ version
################################################################################

import threading
import time
import datetime
import json
import numpy
import uuid
from logger import *
from device_thread import *   #connection to PA or RF Front End
from service_thread import *  #User interface to daemon

class Main_Thread(threading.Thread):
    """ docstring """
    def __init__ (self, cfg, name):
        #super(Main_Thread, self).__init__(name=name)
        threading.Thread.__init__(self)
        threading.current_thread().name = "Main_Thread"
        self.setName("Main_Thread")
        self._stop      = threading.Event()
        self.cfg        = cfg

        self.logger = setup_logger(self.cfg['main_log'])
        self.logger = logging.getLogger(self.cfg['main_log']['name']) #main logger
        self.logger.info("configs: {:s}".format(json.dumps(self.cfg)))

        self.state  = 'BOOT' #BOOT, IDLE, STANDBY, ACTIVE, FAULT, CALIBRATE
        self.state_map = {
            'BOOT':0x00,        #bootup
            'IDLE':0x01,        #threads launched, no connections, attempt md01 connect
            'RX':0x02,          #client connected, device connected, Start loggers
            'TX':0x04,          #client sent PTT!
            'CALIBRATE':0x08,   #calibration mode, future use
            'FAULT':0x80        #some kind of fault has occured
        }

        self.service_con = False #Connection Status, Service Thread
        self.device_con  = False #Connection Status, Device Thread
        self.session_id  = None  #Session ID

        #self.ptt_timer = self.timer = threading.Timer(self.timeout, self.handler)


    def run(self):
        self.logger.info('Launched {:s}'.format(self.name))
        try:
            while (not self._stop.isSet()):
                if self.state == 'BOOT':
                    self._handle_state_boot()
                elif self.state == 'FAULT':
                    self._handle_state_fault()
                else:# NOT in BOOT or FAULT state
                    if self.state == 'IDLE':  self._handle_state_idle()
                    elif self.state == 'RX':  self._handle_state_rx()
                    elif self.state == 'TX':  self._handle_state_tx()
                    elif self.state == 'CALIBRATE':  self._handle_state_calibrate()

        except (KeyboardInterrupt): #when you press ctrl+c
            self.logger.warning('Caught CTRL-C, Terminating Threads...')
            self._stop_threads()
            self.logger.warning('Terminating Main Thread...')
            sys.exit()
        except SystemExit:
            self.logger.warning('Terminating Main Thread...')
        sys.exit()


    #---- STATE HANDLERS -----------------------------------
    def _handle_state_tx(self):
        if ((not self.service_con) or (not self.device_con)):
            #Client or Device disconnected
            if not self.device_con: #Service Thread Disconnected
                self.logger.warning("Device disconnected during TX State.....could be stuck in TX Mode")
                self.logger.warning("May want to Power Cycle Device!")
            #Fallback to IDLE state
            self._set_state('RX')

    def _handle_state_rx(self):
        if ((not self.service_con) or (not self.device_con)):
            #stop child thread loggers
            self._stop_thread_logging()
            #Fallback to IDLE state
            self._set_state('IDLE')
        self._check_thread_queues() #Check for messages from threads
        pass

    def _handle_state_idle(self):
        self._check_thread_queues() #Check for messages from threads
        if ((self.service_con) and (self.device_con)): #Client and Device connected
            session_id = uuid.uuid64()
            ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            #start child thread loggers
            self._start_thread_logging(ts, session_id)
            #Move into RX State
            self._set_state('RX')

    def _handle_state_calibrate(self):
        pass

    def _handle_state_fault(self):
        self.logger.warning("in FAULT state, exiting.......")
        self.logger.warning("Do Something Smarter.......")
        sys.exit()

    def _handle_state_boot(self):
        if self._init_threads():#if all threads activate succesfully
            self.logger.info('Successfully Launched Threads, Switching to IDLE State')
            self._set_state('IDLE')
            time.sleep(1)
        else:
            self.logger.info('Failed to Launched Threads...')
            self._set_state('FAULT')

    #---- END STATE HANDLERS -----------------------------------
    ###############################################################
    #---- CHILD THREAD COMMS HANDLERS & CALLBACKS ----------------------------
    def set_service_con_status(self, status): #called by service thread
        self.service_con = status

    def set_service_con_status(self, status): #called by device thread
        self.device_con = status

    def ptt_received(self, ptt_msg):
        #print json.dumps(ptt_msg, indent=4)
        ts = numpy.datetime64(ptt_msg['uhd']['tx_datetime64'])
        self.sec_to_tx = (numpy.datetime64(datetime.datetime.utcnow()) - ts).item()*1e-9
        if self.state == 'RX':
            self._set_state('TX')
        elif self.state == 'TX':
            self.logger.info('Already in TX, resetting PTT Watchdog')
        else:
            self.logger.info('Not in TX or RX Mode, ignoring....')

    def _check_thread_queues(self):
        #check for service message
        if (self.cfg['thread_enable']['service'] and (not self.service_thread.rx_q.empty())): #Received a message from user
            msg = self.service_thread.rx_q.get()
            self._process_service_message(msg)
        #check for device message
        if (self.cfg['thread_enable']['device'] and (not self.device_thread.rx_q.empty())):
            msg = self.device_thread.rx_q.get()
            self._process_device_message(msg)

    def _process_service_message(self, msg):
        ts = numpy.datetime64(msg['uhd']['tx_datetime64'])
        self.sec_to_tx = (numpy.datetime64(datetime.datetime.utcnow()) - ts).item()*1e-9
        if self.state == 'RX':
            self._set_state('TX')
        elif self.state == 'TX':
            self.logger.info('Already in TX, resetting PTT Watchdog')
        else:
            self.logger.info('Not in TX or RX Mode, ignoring service message....')

    def _send_service_response(self,msg):
        self.service_thread.tx_q.put(msg)
    #---- END CHILD THREAD COMMS HANDLERS & CALLBACKS ----------------------------
    ###############################################################
    #---- THREAD CONTROLS -----------------------------------
    def _start_thread_logging(self, ts, session_id):
        if self.cfg['thread_enable']['service']:
            self.service_thread.start_logging(ts, session_id)
        if self.cfg['thread_enable']['service']:
            self.device_thread.start_logging(ts, session_id)
        pass

    def _stop_thread_logging(self):
        self.service_thread.stop_logging()
        self.device_thread.stop_logging()

    #---- END THREAD CONTROLS -----------------------------------
    ###############################################################
    #---- MAIN THREAD CONTROLS -----------------------------------
    def _set_state(self, state):
        #if ((self.state == 'IDLE') and (state == 'RX')):
            #GOING FROM IDLE TO RX
        self.state = state
        self.logger.info("Connection Status (CLIENT/DEVICE): {0}/{1}".format(self.service_con, self.device_con))
        self.logger.info('Changed STATE to: {:s}'.format(self.state))

    def _init_threads(self):
        try:
            #Initialize Threads
            #print 'thread_enable', self.thread_enable
            self.logger.info("Thread enable: {:s}".format(json.dumps(self.cfg['thread_enable'])))
            for key in self.cfg['thread_enable'].keys():
                if self.cfg['thread_enable'][key]:
                    if key == 'service': #Initialize Service Thread
                        self.logger.info('Setting up Service Thread')
                        if self.cfg['service']['type'] == "TCP":
                            self.service_thread = Service_Thread_TCP(self.cfg['service'], self) #Service Thread
                        self.service_thread.daemon = True
                    elif key == 'device': #Initialize Device Thread
                        self.logger.info('Setting up Device Thread')
                        self.device_thread = device_thread.VHF_UHF_PA_Thread(self.ssid, self.cfg['device'])
                        self.device_thread.daemon = True
            #Launch threads
            for key in self.cfg['thread_enable'].keys():
                if self.cfg['thread_enable'][key]:
                    if key == 'service': #Start Service Thread
                        self.logger.info('Launching Service Thread...')
                        self.service_thread.start() #non-blocking
                    elif key == 'device': #Start Device
                        self.logger.info('Launching Device Thread...')
                        self.device_thread.start() #non-blocking
            return True
        except Exception as e:
            self.logger.error('Error Launching Threads:', exc_info=True)
            self.logger.warning('Setting STATE --> FAULT')
            self._set_state('FAULT')
            return False

    def _stop_threads(self):
        #stop all threads
        for key in self.cfg['thread_enable'].keys():
            if self.cfg['thread_enable'][key]:
                if key == 'service':
                    self.service_thread.stop()
                    self.logger.warning("Terminated Service Thread.")
                    #self.service_thread.join() # wait for the thread to finish what it's doing
                elif key == 'device': #Initialize Radio Thread
                    self.device_thread.stop_thread()
                    self.logger.warning("Terminated Device Thread...")
                    #self.md01_thread.join() # wait for the thread to finish what it's doing

    def _utc_ts(self):
        return "{:s} | main | ".format(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'))

    def stop(self):
        print '{:s} Terminating...'.format(self.name)
        self.logger.info('{:s} Terminating...'.format(self.name))
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
    #---- END MAIN THREAD CONTROLS -----------------------------------
    ###############################################################
