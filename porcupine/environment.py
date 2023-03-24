
""" Environment, defaults """

from os import environ as ENV

ENV.setdefault('LOGLEVEL', 'WARNING')
ENV.setdefault('UPSTREAM', 'http://ai')
ENV.setdefault('REDIS_URL', 'redis://redis')
ENV.setdefault('BIND_ADDR', '0.0.0.0')
ENV.setdefault('BIND_PORT', '8096')
ENV.setdefault('SET_HEADER_HOST', 'ai')
