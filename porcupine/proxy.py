"""

Base proxy class

"""

import logging
import asyncio
import uuid
from time import time
from urllib.parse import urlsplit, urlunsplit, SplitResult
from typing import Final, Optional
import aiodns
import aioredis
from aiohttp.web import BaseRequest, StreamResponse, json_response
from aiohttp.client_reqrep import ClientResponse
from aiohttp import web
from aiohttp.client import ClientSession
from environment import ENV
from multidict import CIMultiDict, CIMultiDictProxy

logger = logging.getLogger(__name__)

class Proxy():
    """ Proxy class """

    def __init__(self):
        self._redis = aioredis.from_url(
            ENV['REDIS_URL'], decode_responses=True,
        )
        self._session_def: Optional[ClientSession] = None
        self._upstream_info: SplitResult = urlsplit(ENV['UPSTREAM'])

    async def _get_upstream_url(self, ipaddr=None):
        """ RR ipaddr in url """

        if not ipaddr:
            ipaddr = (await self._resolver.query(self._upstream_info.hostname, 'A'))[0].host
        netloc = ipaddr
        if self._upstream_info.port:
            netloc += f':{self._upstream_info.port}'

        return urlunsplit((
            self._upstream_info.scheme,
            netloc,
            self._upstream_info.path,
            self._upstream_info.query,
            self._upstream_info.fragment,
        ))

    def _alter_client_headers(self, in_headers: CIMultiDictProxy)  -> CIMultiDictProxy:
        headers: Final = CIMultiDict(in_headers)
        if ENV['SET_HEADER_HOST']:
            headers['Host'] = ENV['SET_HEADER_HOST']
        return CIMultiDictProxy(headers)

    async def _copy_response(
            self, client_request: BaseRequest, upstream_response: ClientResponse
        ) -> StreamResponse:
        """ Create answer response based on upstream response """
        
        client_response = StreamResponse(
            status=upstream_response.status,
            reason=upstream_response.reason,
            headers=upstream_response.headers
        )

        await client_response.prepare(client_request)

        # FIXME: Solve why don't work:
        # chunked = upstream_response.chunked
        chunked = 'chunked' in upstream_response.headers.getall('Transfer-Encoding', [])
        # await client_response.prepare(client_request)
        client_response.content_length = upstream_response.content_length

        buffer = b''
        async for data, eoc in upstream_response.content.iter_chunks():
            buffer += data
            if (chunked and not eoc):
                continue
            await client_response.write(buffer)
            buffer = b''
        else:
            if buffer:
                await client_response.write(buffer)
            await client_response.write_eof()

        return client_response

    async def _direct(self, client_request: BaseRequest):
        """ Link client and server streams maximal transparently """

        method: str = client_request.method
        headers: Final = self._alter_client_headers(client_request.headers)
        url: Final = await self._get_upstream_url() + client_request.path_qs

        if method == 'GET':
            data=None
        else:
            data = client_request.content

        async with self._session_def.request(
            method, url,
            headers=headers,
            data=data,
            ssl=False
        ) as upstream_response:

            return await self._copy_response(client_request, upstream_response)

    async def _upstream_processing_bs(self, client_request: BaseRequest):
        """ handler for certain request """

        url: Final = await self._get_upstream_url() + client_request.path_qs
        headers: Final = self._alter_client_headers(client_request.headers)
        async with self._session_mod.request(
            client_request.method, url,
            headers=headers,
            data=client_request.content,
            ssl=False
        ) as upstream_response:

            if upstream_response.status < 300:
                data = await upstream_response.json()
                origid = data['id_vis']
                uniqid = str(uuid.uuid4())
                data['id_vis'] = uniqid
                await self._redis.hset(f'tgr-vis-{uniqid}', mapping={
                    'ipaddr': urlsplit(url).hostname,
                    'origid': origid,
                    'timebound': int(time()),
                })

                client_response = json_response(
                    data,
                    status=upstream_response.status,
                    reason=upstream_response.reason,
                )
                await client_response.prepare(client_request)

                return client_response

            return self._copy_response(client_request, upstream_response);

    async def _upstream_get_vis(self, client_request: BaseRequest):
        """ handler for certain request """

        uniqid = client_request.match_info['uniqid']
        node_data = await self._redis.hgetall(f'tgr-vis-{uniqid}')
        url: Final = await self._get_upstream_url(node_data['ipaddr']) + \
                f'/recognition/get_vis/{node_data["origid"]}'

        headers: Final = self._alter_client_headers(client_request.headers)
        async with self._session_def.request(
            client_request.method, url,
            headers=headers,
            data=client_request.content,
            ssl=False
        ) as upstream_response:

            return await self._copy_response(client_request, upstream_response)


    async def _serve(self):

        self._session_def = ClientSession(
            connector_owner=True,
            auto_decompress=False,
        )
        self._session_mod = ClientSession(
            connector_owner=True,
            auto_decompress=True,
        )
        self._resolver = aiodns.DNSResolver()
        try:
            app = web.Application(
                client_max_size=100*1024**2,
            )
            routes = web.RouteTableDef()
            app.add_routes(routes)

            app.router.add_routes([
                web.route('POST', '/recognition/processing/byte_stream', self._upstream_processing_bs),
                web.route('GET', '/recognition/get_vis/{uniqid}', self._upstream_get_vis),
                web.route('*', '/{_:.*}', self._direct),
            ])
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, ENV['BIND_ADDR'], int(ENV['BIND_PORT']))
            await site.start()
            await asyncio.Future()
        finally:
            await asyncio.gather(
                self._session_def.close(),
                self._session_mod.close(),
                self._redis.close()
            )

    def start(self):
        """ Start server """

        asyncio.run(self._serve())
