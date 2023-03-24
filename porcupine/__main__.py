#!/usr/bin/env python3

""" 

Porcupine: L7-scaler
Designed for dnsrr

"""

import logging
from environment import ENV

logging.basicConfig(level=ENV['LOGLEVEL'])

if __name__ == "__main__":
    from proxy import Proxy
    try:
        Proxy().start()
    except KeyboardInterrupt:
        pass
