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


PORT = 51413


class Context():

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.port = PORT
        self.peer_id = self._peer_id()
        self.input_type, self.input_string = self._user_input()
        self.raw_inputfile = self._read_file_binary(self.input_string)
        self.peers = []  # do we want to store peers in a list or a dict?

    def _user_input(self):
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

    def _read_file_binary(self, file_path):
        with open(file_path, 'rb') as file_object:
            file = file_object.read()
        return file

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


class Tracker():

    def __init__(self):
        pass


class PeerMessage():

    def __init__(self):
        pass


class Peer():

    def __init__(self):
        pass


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
        self.context.peers = self.make_tracker_request(tracker_url)

    # magnet link
    def handle_magnet_link(self):
        magnet_link = self.context.raw_inputfile.decode('utf-8')
        info_hash, trackers = self.split_magnet_link(magnet_link)
        self.context.info_hash = info_hash
        self.query_dht(info_hash)
        if self.context.has_peers:
            for tracker_url in trackers:
                if tracker_url.startswith('http'):
                    self.make_tracker_request(tracker_url)
                elif tracker_url.startswith('udp'):
                    # TODO: need to handle udp trackers here too
                    pass
                if self.context.has_peers:
                    break

    def split_magnet_link(self, magnet_link):
        magnet_parts = parse_qs(magnet_link)
        trackers = magnet_parts.get('tr')
        hex_hash = magnet_parts['magnet:?xt'][0].lstrip('urn:btih:')
        info_hash = unhexlify(hex_hash)
        return info_hash, trackers

    # DHT
    def query_dht(self):
        pass

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
        # TODO: store tracker id and interval
        self.context.peers = self.format_peer_list(tracker_response[b'peers'])

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
            peer = raw_peer_info[i:i + 6]
            ip = socket.inet_ntoa(peer[:4])
            port = self.unpack_port(peer[4:])
            peer_list.append((ip, port))
        return peer_list

    def unpack_port(self, port):
        return struct.unpack('>H', port)[0]

    # message passing
    def handshake(self):
        prefix = struct.pack('>B', 19)
        name = b'BitTorrent protocol'
        reserved = struct.pack('>8B', *([0] * 8))
        return b''.join((
            prefix,
            name,
            reserved,
            self.context.info_hash,
            self.context.peer_id
        ))

    async def get_file(self):
        peer_tasks = []
        for peer in self.context.peers:
            peer_tasks.append(self.peer_connection(peer))
        await asyncio.gather(*peer_tasks)

    async def peer_connection(self, peer):
        print("Connecting to {}".format(peer))
        ip, port = peer
        try:
            fut = asyncio.open_connection(host=ip, port=port)
            reader, writer = await asyncio.wait_for(fut, timeout=5)
        except ConnectionRefusedError:
            print("Connection to {} refused".format(ip))
            return
        except asyncio.TimeoutError:
            print("Connection to {} timed out".format(ip))
            return
        # handshake
        handshake = self.handshake()
        writer.write(handshake)
        await writer.drain()
        resp = await reader.read()
        print(resp)
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
