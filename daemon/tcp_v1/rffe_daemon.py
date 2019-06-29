#!/usr/bin/env python
################################################################################
#   Title: RF Front End Control Daemon
# Project: VTGS
# Version: 1.0.0
#    Date: Aug 26, 2018
#  Author: Zach Leffke, KJ4QLP
# Comments:
#   -RF Front End Control Daemon
#   -Intended for use with systemd
#   -Starting with TCP, but intend to add RMQ version
################################################################################

import math
import string
import time
import sys
import os
import datetime
import logging
import json

#from optparse import OptionParser
from main_thread import *
import argparse


def main():
    """ Main entry point to start the service. """

    startup_ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    #--------START Command Line argument parser------------------------------------------------------
    parser = argparse.ArgumentParser(description="RF Frond End Control Daemon",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    cwd = os.getcwd()
    cfg_fp_default = '/'.join([cwd, 'config'])
    cfg = parser.add_argument_group('Daemon Configuration File')
    cfg.add_argument('--cfg_path',
                       dest='cfg_path',
                       type=str,
                       default='/'.join([os.getcwd(), 'config']),
                       help="Daemon Configuration File Path",
                       action="store")
    cfg.add_argument('--cfg_file',
                       dest='cfg_file',
                       type=str,
                       default="rffe_config_fed-vu.json",
                       help="Daemon Configuration File",
                       action="store")

    args = parser.parse_args()
    #--------END Command Line argument parser------------------------------------------------------
    os.system('reset')
    fp_cfg = '/'.join([args.cfg_path,args.cfg_file])
    if not os.path.isfile(fp_cfg) == True:
        print 'ERROR: Invalid Configuration File: {:s}'.format(fp_cfg)
        sys.exit()
    print 'Importing configuration File: {:s}'.format(fp_cfg)
    with open(fp_cfg, 'r') as json_data:
        cfg = json.load(json_data)
        json_data.close()
    cfg['startup_ts'] = startup_ts

    log_name = '.'.join([cfg['ssid'],cfg['daemon_name'],'main'])
    cfg['main_log'].update({
        "path":cfg['log_path'],
        "name":log_name,
        "startup_ts":startup_ts
    })

    for key in cfg['thread_enable'].keys():
        cfg[key].update({
            'ssid':cfg['ssid'],
            'log_path':cfg['log_path'],
            'main_log':log_name,
            'startup_ts':startup_ts
        })

    print json.dumps(cfg, indent=4)

    main_thread = Main_Thread(cfg, name="Main_Thread")
    main_thread.daemon = True
    main_thread.run()
    sys.exit()


if __name__ == '__main__':
    main()
