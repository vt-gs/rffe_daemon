#!/usr/bin/env python
#################################################
#   Title: MD01 Class                           #
# Project: VTGS Tracking Daemon                 #
# Version: 3.                                   #
#    Date: Aug 03, 2016                         #
#  Author: Zach Leffke, KJ4QLP                  #
# Comment: This version of the Tracking Daemon  #
#           is intended to be a 1:1 interface   #
#           for the MD01.  It will run on the   #
#           Control Server 'eddie' and provide  #
#           a single interface to the MD01      #
#           controllers.                        #
#           This daemon is a protocol translator#
#################################################

import socket
import os
import string
import sys
import time
import threading
import binascii
import datetime
import logging
import numpy

class VHF_UHF_Power_Amplifier(object):
    """docstring for ."""
    def __init__ (self, cfg, parent = None):
        self._init_tm()
        self._init_tc()
        self.cfg = cfg


        self.status = {
            'connected':False,
            'ts':None
        }

        self.connected = False
        print 'initialized power amp class'

    def connect(self):
        #connect to md01 controller
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP Socket
        self.sock.settimeout(self.cfg['timeout'])   #set socket timeout
        try:
            self.sock.connect((self.cfg['ip'], self.cfg['port']))
            time.sleep(0.1)
            self.connected = True
            return self.connected
        except socket.error as msg:
            #self.logger.info("Failed to connected to MD01 at [{:s}:{:d}]: {:s}".format(self.ip, self.port, msg))
            self.sock.close()
            self.connected = False
            #self.status['connected'] = self.connected
            #self.status['ts'] = None #clear rx timestamp
            return self.connected

    def disconnect(self):
        #disconnect from md01 controller
        #print self.getTimeStampGMT() + "MD01 |  Attempting to disconnect from MD01 Controller"
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.connected = False
        return self.connected

    def get_telemetry(self):
        self.connected = self._send_amp_tc('query')
        return self.tm

    def set_tx_mode(self, mode):
        if mode == 'UHF': self.connected = self._send_amp_tc('uhf_tx')
        if mode == 'VHF': self.connected = self._send_amp_tc('vhf_tx')

    def set_rx_mode(self):
        self.connected = self._send_amp_tc('rx_all')


    def _send_amp_tc(self, cmd):
        if (not self.connected):
            return self.connected
        else:
            try:
                if cmd in self.tc.keys(): #verify allowable command
                    self.tc_msg = self.tc[cmd]
                    if self.tc_msg:
                        self.sock.sendall(self.tc_msg)
                        feedback = self._recv_data()
                        #print feedback
                        if self.tc_msg == 'q':
                            self._parse_query_feedback(feedback.strip())
                            return self.connected
                        #self.logger.info('Sent command to amp: {:s}'.format(cmd))
            except socket.error as e:
                self._Handle_Socket_Exception(e)
            return self.connected #return 0 good status, feedback az/el




    def _recv_data(self):
        #reset RX Timestamp
        self.status['ts'] = None
        self.status['connected'] = True
        #receive socket data
        feedback = ''
        while True: #cycle through recv buffer
            c = self.sock.recv(1)
            if self.tc_msg == c: #amp should exho command
                if self.tc_msg in ['v','u','r']:break
                flag = True
                while flag: #continue cycling through receive buffer
                    c = self.sock.recv(1)
                    #print c, binascii.hexlify(c)
                    if c == '\n': #detect end of line
                        feedback += c
                        flag = False
                    else:
                        feedback += c
                break
        #print binascii.hexlify(feedback)
        return feedback

    def _Handle_Socket_Exception(self, e):
        #self.logger.info("Socket Exception Thrown: {:s}".format(str(e)))
        #self.logger.info("Shutting Down Socket...")
        self.sock.close()
        self.connected = False
        #self._set_bad_status()

    def _set_bad_status(self):
        print self._utc_ts() + 'bad status'
        self.status['ts'] = None
        self.status['connected'] = False
        self.status['cur_az'] = 0.0
        self.status['cur_el'] = 0.0
        return self.status


    def get_tc_msg(self, tc):
        if tc in self.tc.keys(): #check that command is in TC keys
            return self.tc[tc]
        else:
            return -1 #return negative indicator

    def _parse_query_feedback(self, data):
        data = data.split(',')
        #print data
        try:
            self.tm['uptime']           = int(data[1])
            self.tm['reset_count']      = int(data[2])
            self.tm['pa_state']         = data[3]

            self.tm['temp']['current']  = float(data[4])
            self.tm['temp']['case']     = float(data[5])
            self.tm['temp']['amplifier']= float(data[6])

            self.tm['bus']['shunt_mv']  = float(data[7])
            self.tm['bus']['bus_v']     = float(data[8])
            self.tm['bus']['bus_ma']    = float(data[9])

            self.tm['rf']['pa_fwd_mv']  = float(data[10])
            self.tm['rf']['pa_rev_mv']  = float(data[11])
            self.tm['rf']['pa_fwd_pwr'] = float(data[12])
            self.tm['rf']['pa_rev_pwr'] = float(data[13])
            self.tm['rf']['vswr']       = float(data[14])

            self.tm['btn']['red']       = bool(int(data[15]))
            self.tm['btn']['black']     = bool(int(data[16]))

            self.tm['alert']['thermo']  = bool(int(data[17]))
            self.tm['alert']['current'] = bool(int(data[18]))
            self.tm['alert']['temp']    = bool(int(data[19]))

            self.tm['status']['fan']            = bool(int(data[20]))
            self.tm['status']['pwr_rel']        = bool(int(data[21]))
            self.tm['status']['vhf_coax_rel']   = bool(int(data[22]))
            self.tm['status']['uhf_coax_rel']   = bool(int(data[23]))
            self.tm['status']['vhf_ptt_out']    = bool(int(data[24]))
            self.tm['status']['uhf_ptt_out']    = bool(int(data[25]))
            self.tm['status']['cal_mode']       = bool(int(data[26]))
            return True
        except Exception as e:
            return False


    def _init_tm(self):
        self.tm = {
            'uptime'        :0,
            'reset_count'   :0,
            'pa_state'      :"",
            'temp':{
                'current'   :0.0,
                'case'      :0.0,
                'amplifier' :0.0,
            },
            'bus':{
                'shunt_mv'  :0.0,
                'bus_v'     :0.0,
                'bus_ma'    :0.0
            },
            'rf':{
                'pa_fwd_mv' :0.0,
                'pa_rev_mv' :0.0,
                'pa_fwd_pwr':0.0,
                'pa_rev_pwr':0.0,
                'vswr'      :0.0
            },
            'btn':{
                'red':False,
                'black':False
            },
            'alert':{
                'thermo' :False,
                'current':False,
                'temp'   :False
            },
            'status':{
                'fan':False,
                'pwr_rel':False,
                'vhf_coax_rel':False,
                'uhf_coax_rel':False,
                'vhf_ptt_out':False,
                'uhf_ptt_out':False,
                'cal_mode':False
            }
        }

    def _init_tc(self):
        self.tc = {
            'query':'q',
            'rx_all':'r',
            'vhf_tx':'v',
            'uhf_tx':'u',
            'fan_manual':'f',
            'clear_eeprom':'c',
            'read_eeprom':'e',
            'sketch_vers':'s'
        }
