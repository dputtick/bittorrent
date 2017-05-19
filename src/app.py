#!/usr/bin/env python3

import asyncio
import random

from hashlib import sha1
from urllib.parse import urlencode

import bencode
import aiohttp


def read_file_binary(file_path):
    with open(file_path, 'rb') as file_object:
        file = file_object.read()
    return file


def info_hash(metafile_info):
    encoded = bencode.bencode(metafile_info)
    metafile_info_hash = sha1(encoded).digest()
    return metafile_info_hash


def make_tracker_params(context):
    metafile_data = bencode.bdecode(context['raw_metafile'])
    tracker_base_url = metafile_data[b'announce'].decode('utf-8')
    file_info = metafile_data[b'info']
    context['info_hash'] = info_hash(file_info)
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
    return compose_url(tracker_base_url, request_params)


def compose_url(base_url, request_params):
    return base_url + '?' + urlencode(request_params)


def make_peer_id():
    lead_string = '000000'
    random_digits = ''.join([str(random.randint(0, 9)) for _ in range(14)])
    return lead_string + random_digits


async def make_tracker_request(tracker_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(tracker_url) as response:
            response_bytes = await response.read()
            response_dict = bencode.bdecode(response_bytes)
            return response_dict


def peer_list(raw_peer_info):
    peer_list = []
    for i in range(0, len(raw_peer_info), 6):
        chunk = raw_peer_info[i:i + 6]
        ip = '{}.{}.{}.{}'.format(*chunk[0:4])
        port = chunk[4] * 256 + chunk[5]
        peer_list.append((ip, port))
    return peer_list


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


def split_magnet_link(magnet_link):
    pass


def get_metadata(context):
    if context['input_type'] is 'magnet':
        magnet_link = read_file_binary(context['input_string'])
        info_hash, trackers = split_magnet_link(magnet_link)
        # try looking for info hash in the dht
        # if that doesn't work, then try the trackers in order
    elif context['input_type'] is 'torrent':
        context['raw_metafile'] = read_file_binary(context['input_string'])
        tracker_request_url = make_tracker_params(context)
        tracker_coro = make_tracker_request(tracker_request_url)
        tracker_task = context['loop'].create_task(tracker_coro)
        tracker_response = context['loop'].run_until_complete(tracker_task)
        peers = peer_list(tracker_response[b'peers'])
        context['peers'] = peers


def setup_context():
    input_type, input_string = user_input()
    loop = asyncio.get_event_loop()
    context = {
        'input_type': input_type,
        'input_string': input_string,
        'peer_id': make_peer_id(),
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


def main():
    context = setup_context()
    get_metadata(context)
    file_coro = get_file(context)
    main_task = context['loop'].create_task(file_coro)
    context['loop'].run_until_complete(main_task)


if __name__ == '__main__':
    main()
