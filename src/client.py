#!/usr/bin/env python3

import asyncio
import datetime
import struct
import socket
import argparse

from hashlib import sha1
from urllib.parse import urlencode, parse_qs
from binascii import unhexlify

import bencode
import aiohttp


PORT = 51500


class Context():

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.port = PORT
        self.peer_id = self._peer_id()
        self.peers = {}
        self.trackers = {}

    def _peer_id(self):
        lead_string = b'000000'
        date_today = datetime.date.today().isoformat()
        date_hash = bytes(sha1(date_today.encode()).hexdigest()[:14], 'utf-8')
        return lead_string + date_hash

    @property
    def has_peers(self):
        if self.peers:
            return True
        elif not self.peers:
            return False
        else:
            raise RuntimeError("Error with peer list")

    def add_peers(self, *new_peers):
        for peer in new_peers:
            ip, port = peer
            if ip not in self.peers:
                self.peers[ip] = Peer(ip, port, self)

    def add_trackers(self, *new_trackers):
        for tracker in new_trackers:
            if tracker.address not in self.trackers:
                self.trackers[tracker.address] = Tracker(tracker, self)


class Tracker():

    def __init__(self, address, context):
        self.address = address
        self.context = context

    @property
    def protocol(self):
        if self.address.startswith('udp'):
            return 'udp'
        if self.address.startswith('http'):
            return 'tcp'

    def make_request(self):
        if self.protocol is 'tcp':
            return self.tcp_request()
        elif self.protocol is 'udp':
            return None
            # return self.udp_request()

    def udp_request(self):
        raise NotImplemented('Client does not handle udp trackers yet')

    def tcp_request(self):
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
        request_url = self.compose_url(self.address, request_params)
        tracker_coro = self.http_request(request_url)
        tracker_task = self.context.loop.create_task(tracker_coro)
        response_bytes = self.context.loop.run_until_complete(tracker_task)
        tracker_response = bencode.bdecode(response_bytes)
        # TODO: store tracker id and interval for repeat connections
        return self.format_peer_list(tracker_response[b'peers'])

    def compose_url(self, base_url, request_params):
        return base_url + '?' + urlencode(request_params)

    def format_peer_list(self, raw_peer_info):
        peer_list = []
        for i in range(0, len(raw_peer_info), 6):
            peer = raw_peer_info[i:i + 6]
            ip = socket.inet_ntoa(peer[:4])
            port = self.unpack_port(peer[4:])
            peer_list.append((ip, port))
        return peer_list

    def unpack_port(self, port):
        return struct.unpack('>H', port)[0]

    async def http_request(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_bytes = await response.read()
                return response_bytes


class Peer():

    def __init__(self, address, port, context):
        self.address = address
        self.port = port
        self.context = context
        self.choked = True
        self.interested = False

    async def peer_connection(self):
        print("{}: connecting".format(self.address))
        try:
            fut = asyncio.open_connection(host=self.address, port=self.port)
            self.reader, self.writer = await asyncio.wait_for(fut, timeout=5)
        except ConnectionRefusedError:
            print("{}: connection refused".format(self.address))
            return
        except asyncio.TimeoutError:
            print("{} connection timed out".format(self.address))
            return
        # handshake
        handshake_resp = await self.handshake()
        print(handshake_resp)
        self.id = self.parse_handshake(handshake_resp)
        # determine pieces/blocks that the peer has
        # check if those are in the set of pieces

    def parse_handshake(self, handshake_resp):
        peer_id = handshake_resp[28:48]
        return peer_id
        # Length = 1 byte
        # Procotol = 19 bytes
        # 8 bytes
        # 20 bytes
        # 20 bytes

    async def handshake(self):
        handshake = struct.pack(
            '>B19s8x20s20s',
            19,
            b'BitTorrent protocol',
            self.context.info_hash,
            self.context.peer_id)
        self.writer.write(handshake)
        print('{}: handshake sent'.format(self.address))
        await self.writer.drain()
        print('{}: handshake drained'.format(self.address))
        resp = await self.reader.read()
        return resp

    def keep_alive():
        return b''

    async def send_message(self, message):
        self.writer.write(message)
        await self.writer.drain()


class Client():

    def __init__(self):
        self.context = Context()

    def user_input(self):
        parser = argparse.ArgumentParser(description="Take user input")
        parser.add_argument('-m', dest="magnet", help="Magnet link")
        parser.add_argument('-t', dest="torrent", help="Torrent file")
        args = parser.parse_args()
        if args.magnet:
            input_type = 'magnet'
            input_path = args.magnet
        elif args.torrent:
            input_type = 'torrent'
            input_path = args.torrent
        return input_type, input_path

    # .torrent file
    def read_file_binary(self, file_path):
        with open(file_path, 'rb') as file_object:
            file = file_object.read()
        return file

    def info_hash(self, metafile_info):
        encoded = bencode.bencode(metafile_info)
        metafile_info_hash = sha1(encoded).digest()
        return metafile_info_hash

    def split_piece_hashes(self, pieces):
        return [pieces[i:i + 20] for i in range(0, len(pieces), 20)]

    # magnet link
    def split_magnet_link(self, magnet_link):
        magnet_parts = parse_qs(magnet_link)
        trackers = magnet_parts.get('tr')
        hex_hash = magnet_parts['magnet:?xt'][0].lstrip('urn:btih:')
        info_hash = unhexlify(hex_hash)
        return info_hash, trackers

    # DHT
    def query_dht(self):
        pass

    # Peer communication
    async def get_file(self):
        peer_coros = [peer.peer_connection() for peer in self.context.peers.values()]
        await asyncio.gather(*peer_coros)

    def run(self):
        input_type, input_string = self.user_input()
        if input_type is 'torrent':
            raw_metafile = self.read_file_binary(input_string)
            metafile = bencode.bdecode(raw_metafile)
            tracker_url = metafile[b'announce'].decode('utf-8')
            self.context.add_trackers(tracker_url)
            info_dict = metafile[b'info']
            self.context.info_hash = self.info_hash(info_dict)
            self.context.piece_hashes = self.split_piece_hashes(info_dict[b'pieces'])
            self.context.name = info_dict[b'name']
        elif input_type is 'magnet':
            self.context.info_hash, tracker_urls = self.split_magnet_link(input_string)
            self.context.add_trackers(*tracker_urls)
        self.query_dht()
        for tracker in self.context.trackers.values():
            peers = tracker.make_request()
            self.context.add_peers(*peers)
        file_coro = self.get_file()
        main_task = self.context.loop.create_task(file_coro)
        self.context.loop.run_until_complete(main_task)


def main():
    client = Client()
    client.run()


if __name__ == '__main__':
    main()
