#!/usr/bin/env python3

import asyncio
import random

from hashlib import sha1
from urllib.parse import urlencode, parse_qs
from binascii import unhexlify

import bencode
import aiohttp


class Context():

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.port = 6881
        self.peer_id = self._peer_id()
        self.input_type, self.input_string = self._user_input()
        self.raw_inputfile = self._read_file_binary(self.input_string)

    def _user_input(self):
        input_type = 'magnet'
        input_string = 'magnet_link.txt'
        # input_type = 'torrent'
        # input_string = 'sample.torrent'
        return input_type, input_string

    def _read_file_binary(self, file_path):
        with open(file_path, 'rb') as file_object:
            file = file_object.read()
        return file

    def _peer_id(self):
        lead_string = '000000'
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(14)])
        return lead_string + random_digits


class Client():

    def __init__(self):
        self.context = Context()

    def info_hash(self, metafile_info):
        encoded = bencode.bencode(metafile_info)
        metafile_info_hash = sha1(encoded).digest()
        return metafile_info_hash

    def get_metadata(self):
        if self.context.input_type is 'magnet':
            self.handle_magnet_link()
        elif self.context.input_type is 'torrent':
            self.handle_torrent_file()

    # .torrent file
    def handle_torrent_file(self):
        metafile_data = bencode.bdecode(self.context.raw_inputfile)
        tracker_url = metafile_data[b'announce'].decode('utf-8')
        file_info = metafile_data[b'info']
        self.context.info_hash = self.info_hash(file_info)
        self.context.peers = self._tracker_request(tracker_url)

    # magnet link
    def handle_magnet_link(self):
        magnet_link = self.context.raw_inputfile.decode('utf-8')
        info_hash, trackers = self.split_magnet_link(magnet_link)
        self.context.info_hash = info_hash
        peers = self.query_dht(info_hash)
        if len(peers) == 0:
            for tracker_url in trackers:
                # TODO: handle udp trackers
                peers = self.make_tracker_request(tracker_url)
                if peers:
                    break
        self.context.peers = peers

    def split_magnet_link(self, magnet_link):
        magnet_parts = parse_qs(magnet_link)
        trackers = magnet_parts.get('tr')
        hex_hash = magnet_parts['magnet:?xt'][0].lstrip('urn:btih:')
        binary_hash = unhexlify(hex_hash)
        return binary_hash, trackers

    # DHT
    def query_dht(self, info_hash):
        return []

    # tracker request
    def make_tracker_request(self, tracker_url):
        request_params = {
            'info_hash': self.context.info_hash,
            'peer_id': self.context.peer_id,
            'port': self.context.port,
            'uploaded': 0,
            'downloaded': 0,
            'left': 0,
            'compact': 1,
            'event': 'started'
        }
        tracker_request_url = self.compose_url(tracker_url, request_params)
        tracker_coro = self.http_request(tracker_request_url)
        tracker_task = self.context.loop.create_task(tracker_coro)
        response_bytes = self.context.loop.run_until_complete(tracker_task)
        tracker_response = bencode.bdecode(response_bytes)
        return self.format_peer_list(tracker_response[b'peers'])

    def compose_url(self, base_url, request_params):
        return base_url + '?' + urlencode(request_params)

    async def http_request(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_bytes = await response.read()
                return response_bytes

    def format_peer_list(self, raw_peer_info):
        peer_list = []
        for i in range(0, len(raw_peer_info), 6):
            chunk = raw_peer_info[i:i + 6]
            ip = '{}.{}.{}.{}'.format(*chunk[0:4])
            port = chunk[4] * 256 + chunk[5]
            peer_list.append((ip, port))
        return peer_list

    # message passing
    async def get_file(self):
        peer_tasks = []
        for peer in self.context.peers:
            peer_tasks.append(self.peer_connection(peer))
        await asyncio.gather(*peer_tasks)

    async def peer_connection(self, peer):
        print("Connecting to {}".format(peer))
        ip, port = peer
        reader, writer = await asyncio.open_connection(host=ip, port=port)
        # determine pieces/blocks that the peer has
        # check if those are in the set of pieces

    async def get_piece(self):
        pass

    def run(self):
        self.get_metadata()
        file_coro = self.get_file()
        main_task = self.context.loop.create_task(file_coro)
        self.context.loop.run_until_complete(main_task)


def main():
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
