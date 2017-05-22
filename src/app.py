#!/usr/bin/env python3

import asyncio
import random

from hashlib import sha1
from urllib.parse import urlencode, parse_qs
from binascii import unhexlify

import bencode
import aiohttp


# setup
def setup_context():
    input_type, input_string = user_input()
    loop = asyncio.get_event_loop()
    context = {
        'input_type': input_type,
        'input_string': input_string,
        'peer_id': peer_id(),
        'raw_metafile': None,
        'info_hash': None,
        'port': 6881,
        'loop': loop
    }
    return context


def user_input():
    input_type = 'magnet'
    input_string = 'magnet_link.txt'
    # input_type = 'torrent'
    # input_string = 'sample.torrent'
    return input_type, input_string


def read_file_binary(file_path):
    with open(file_path, 'rb') as file_object:
        file = file_object.read()
    return file


def info_hash(metafile_info):
    encoded = bencode.bencode(metafile_info)
    metafile_info_hash = sha1(encoded).digest()
    return metafile_info_hash


def peer_id():
    lead_string = '000000'
    random_digits = ''.join([str(random.randint(0, 9)) for _ in range(14)])
    return lead_string + random_digits


def get_metadata(context):
    if context['input_type'] is 'magnet':
        handle_magnet_link(context)
    elif context['input_type'] is 'torrent':
        handle_torrent_file(context)


# .torrent file
def handle_torrent_file(context):
    context['raw_metafile'] = read_file_binary(context['input_string'])
    metafile_data = bencode.bdecode(context['raw_metafile'])
    tracker_url = metafile_data[b'announce'].decode('utf-8')
    file_info = metafile_data[b'info']
    context['info_hash'] = info_hash(file_info)
    context['peers'] = make_tracker_request(context, tracker_url)


# magnet link
def handle_magnet_link(context):
    magnet_link = read_file_binary(context['input_string']).decode()
    context['info_hash'], trackers = split_magnet_link(magnet_link)
    peers = query_dht(context['info_hash'])
    if len(peers) == 0:
        for tracker in trackers:
            peers = make_tracker_request(context, tracker)
            if peers:
                print(peers)
                break
    context['peers'] = peers
    # if that doesn't work, then try the trackers in order


def split_magnet_link(magnet_link):
    magnet_parts = parse_qs(magnet_link)
    trackers = magnet_parts.get('tr')
    hex_hash = magnet_parts['magnet:?xt'][0].lstrip('urn:btih:')
    binary_hash = unhexlify(hex_hash)
    return binary_hash, trackers


# DHT
def query_dht(info_hash):
    return []


# tracker request
def make_tracker_request(context, tracker_url):
    request_params = {
        'info_hash': context['info_hash'],
        'peer_id': context['peer_id'],
        'port': context['port'],
        'uploaded': 0,
        'downloaded': 0,
        'left': 0,
        'compact': 1,
        'event': 'started'
    }
    tracker_request_url = compose_url(tracker_url, request_params)
    tracker_coro = http_request(tracker_request_url)
    tracker_task = context['loop'].create_task(tracker_coro)
    response_bytes = context['loop'].run_until_complete(tracker_task)
    tracker_response = bencode.bdecode(response_bytes)
    return peer_list(tracker_response[b'peers'])


def compose_url(base_url, request_params):
    return base_url + '?' + urlencode(request_params)


async def http_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_bytes = await response.read()
            return response_bytes


def peer_list(raw_peer_info):
    peer_list = []
    for i in range(0, len(raw_peer_info), 6):
        chunk = raw_peer_info[i:i + 6]
        ip = '{}.{}.{}.{}'.format(*chunk[0:4])
        port = chunk[4] * 256 + chunk[5]
        peer_list.append((ip, port))
    return peer_list


# message passing
async def get_file(context):
    peers = context['peers']
    peer_tasks = []
    for peer in peers:
        peer_tasks.append(peer_connection(peer, context))
    await asyncio.gather(*peer_tasks)


async def peer_connection(peer, context):
    print("Connecting to {}".format(peer))
    ip, port = peer
    reader, writer = await asyncio.open_connection(host=ip, port=port)
    # determine pieces/blocks that the peer has
    # check if those are in the set of pieces


async def get_piece():
    pass


# main
def main():
    context = setup_context()
    get_metadata(context)
    file_coro = get_file(context)
    main_task = context['loop'].create_task(file_coro)
    context['loop'].run_until_complete(main_task)


if __name__ == '__main__':
    main()
