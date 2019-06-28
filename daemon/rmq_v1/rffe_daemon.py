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
    parser = argparse.ArgumentParser(description="RF Frond End Control Daemon")

    cfg = parser.add_argument_group('Daemon Configuration File')
    cfg.add_argument('--cfg_path',
                       dest='cfg_path',
                       type=str,
                       default=os.getcwd(),
                       help="Daemon Configuration File Path",
                       action="store")
    cfg.add_argument('--cfg_file',
                       dest='cfg_file',
                       type=str,
                       default="rffe_config_tcp_vu.json",
                       help="Daemon Configuration File",
                       action="store")

    args = parser.parse_args()
    #--------END Command Line argument parser------------------------------------------------------

    fp_cfg = '/'.join([args.cfg_path,args.cfg_file])
    print fp_cfg
    if not os.path.isfile(fp_cfg) == True:
        print 'ERROR: Invalid Configuration File: {:s}'.format(fp_cfg)
        sys.exit()
    print 'Importing configuration File: {:s}'.format(fp_cfg)
    with open(fp_cfg, 'r') as json_data:
        cfg = json.load(json_data)
        json_data.close()
    cfg['startup_ts'] = startup_ts
    print cfg

    main_thread = Main_Thread(cfg)
    main_thread.daemon = True
    main_thread.run()
    sys.exit()


if __name__ == '__main__':
    main()
