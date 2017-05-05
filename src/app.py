#!/usr/bin/env python3


import asyncio

import bencoder
import aiohttp


async def download_torrent(torrent_file_path):
    with open('test.torrent', 'rb') as file_object:
        file = file_object.read()
    await parse_torrent_file(file)


async def parse_torrent_file(file):
    metafile_data = bencoder.decode(file)
    tracker_url = metafile_data[b'announce'].decode('utf-8')
    await connect_tracker(tracker_url)


async def connect_tracker(tracker_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(tracker_url) as resp:
            print(resp.status)
            print(await resp.text())


def main():
    loop = asyncio.get_event_loop()
    torrent_file_path = 'test.torrent'
    task = loop.create_task(download_torrent(torrent_file_path))
    loop.run_until_complete(task)


if __name__ == '__main__':
    main()
