import asyncio
import aiohttp
from multiprocessing import Queue, Process
import time

# Simulated list of image URLs
urls = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/June_odd-eyed-cat_cropped.jpg/320px-June_odd-eyed-cat_cropped.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Kittyply_edit1.jpg/320px-Kittyply_edit1.jpg",
    # Add more image URLs here
]

# Worker that just prints queue item size (for testing)
def queue_reader(queue):
    while True:
        item = queue.get()
        if item is None:
            break
        print(f"Received chunk of size: {len(item)} bytes")

# Asynchronous fetcher
async def fetch_chunk(session, url, queue):
    async with session.get(url) as resp:
        data = await resp.read()
        queue.put(data)
        print(f"Fetched {url} ({len(data)} bytes)")

# Launch all fetches
async def fetch_megachunk(urls, queue):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_chunk(session, url, queue) for url in urls]
        await asyncio.gather(*tasks)

# Main function to tie it together
def main():
    queue = Queue()

    # Start a simple reader process for testing
    reader = Process(target=queue_reader, args=(queue,))
    reader.start()

    # Fetch chunks and fill queue
    asyncio.run(fetch_megachunk(urls, queue))

    # Signal reader to stop
    queue.put(None)
    reader.join()

if __name__ == "__main__":
    main()