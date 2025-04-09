#!/usr/bin/python3

import PIL.Image
import sys, io, os
import datetime
import asyncio
import aiohttp
import cv2
import numpy as np
import platform
from concurrent.futures import ThreadPoolExecutor
import time
import re
from multiprocessing import Process, Queue, cpu_count
import urllib.request
import json

USER_AGENT = "pmfun naziFinder 0.10.0 " + ' '.join(sys.argv[1:])
PPFUN_URL = "https://pixmap.fun"
PPFUN_STORAGE_URL = "https://backup.pixmap.fun"

file_lock = asyncio.Lock()

def clear_screen():
    system_name = platform.system()
    if system_name == "Windows":
        os.system('cls')
    else:
        os.system('clear')

# Fetches the user data to use
def fetchMe():
    url = f"{PPFUN_URL}/api/me"
    headers = {
      'User-Agent': USER_AGENT
    }
    attempts = 0
    while True:
        try:
            # Create a request with the necessary headers
            req = urllib.request.Request(url, headers=headers)
            # Send the request and read the response
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                return data
        except Exception as e:
            if attempts > 3:
                print(f"Could not get {url} in three tries, cancelling")
                raise
            attempts += 1
            print(f"Failed to load {url}, trying again in 5s: {e}")
            time.sleep(5)  # Sleep 5 seconds before retrying
            
# Gets the chunk (fraction of megachunk)
async def fetch_chunk(session, url, offx, offy, image, bkg, needed = False):
    attempts = 0
    headers = {
      'User-Agent': USER_AGENT
    }
    while True:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    if needed:
                        img = PIL.Image.new('RGB', (256, 256), color=bkg)
                        image.paste(img, (offx, offy))
                        img.close()
                    return
                if resp.status != 200:
                    if needed:
                        continue
                    return
                data = await resp.read()
                img = PIL.Image.open(io.BytesIO(data)).convert('RGBA')
                image.paste(img, (offx, offy), img)
                img.close()
                return
        except:
            if attempts > 3:
                raise
            attempts += 1
            pass

def get_lut_index(LUT, target_color):
    # Use np.all to check for exact match across all 3 channels
    for idx, color in enumerate(LUT):
        if np.array_equal(color, target_color):  # Check if the colors match
            return idx
    return -1  # Return -1 if no match is found

def convert_to_indexed(image, lut):

    # Create an indexed image with the same shape as the input image
    H, W, _ = image.shape
    indexed_image = np.zeros((H, W), dtype=np.uint8)

    # Use broadcasting and vectorized approach to find matching BGR values
    for color_tuple, index in lut.items():
        mask = np.all(image == color_tuple, axis=-1)  # Create a mask for pixels matching the color tuple
        indexed_image[mask] = index  # Assign the index to matching pixels
    return indexed_image

# Gets the megachunk
async def fetch_megachunk(canvas_id, canvas, x, y, w, h, start_date, end_date, taskNumber, searchable_colors_BGR, swastikas_swas, swastikas_name, display_length, batchSize, queue):
    print(f"Processing mega-chunk #{taskNumber} at ({x}, {y}) with width {w} and height {h}...")
    
    canvas_size = canvas["size"] # The size of the megachunk
    bkg = tuple(canvas['colors'][0]) # The background color
    iter_date = start_date.strftime("%Y%m%d") # The date e.g. 20250408

    # Calculates the chunk to get
    offset = int(-canvas_size / 2)
    xc = (x - offset) // 256
    wc = (x + w - offset) // 256
    yc = (y - offset) // 256
    hc = (y + h - offset) // 256

    # Calls and loads the chunk
    tasks = []
    async with aiohttp.ClientSession() as session:

        print(f"Getting megachunk #{taskNumber}...")
        # Gets megachunk
        image = PIL.Image.new('RGBA', (w, h)) # Fallback. If neither day loads, it matches on a blank megchunk
        for iy in range(yc, hc + 1):
            for ix in range(xc, wc + 1):
                url = '%s/%s/%s/%s/%s/tiles/%s/%s.png' % (PPFUN_STORAGE_URL, iter_date[0:4], iter_date[4:6], iter_date[6:], canvas_id, ix, iy)
                #print(f"Attempting GET at {url}")
                offx = ix * 256 + offset - x
                offy = iy * 256 + offset - y
                tasks.append(fetch_chunk(session, url, offx, offy, image, bkg, True))
        await asyncio.gather(*tasks)

        # check if image is all just one color to lazily detect if whole full backup was 404
        clr = image.getcolors(1)
        if clr is not None:
            tasks = []

            print(f"The megachunk at ({x}, {y}) for today (the {int(iter_date[6:])}th) is faulty, using yesterday's (the {int(iter_date[6:])-1}th) megachunk instead.")
            
            # Rolls back the date 1 day
            iter_date = iter_date[:6] + str(int(iter_date[6:])-1).zfill(2)
            
            for iy in range(yc, hc + 1):
                for ix in range(xc, wc + 1):
                    url = '%s/%s/%s/%s/%s/tiles/%s/%s.png' % (PPFUN_STORAGE_URL, iter_date[0:4], iter_date[4:6], iter_date[6:], canvas_id, ix, iy)
                    #print(f"Attempting GET at {url}")
                    offx = ix * 256 + offset - x
                    offy = iy * 256 + offset - y
                    tasks.append(fetch_chunk(session, url, offx, offy, image, bkg, True))
            await asyncio.gather(*tasks)
        queue.put((taskNumber, image))
        print(f"Fetched megachunk #{taskNumber}")
        #image.close()

async def image_processing(taskNumber, searchable_colors_BGR, image, swastikas_swas, swastikas_name):
    print(f"#{taskNumber} mapping LUT")

    lut = {} # Custom Look-Up Table

    # Maps the LUT
    for index, currentPalleteColor in enumerate(searchable_colors_BGR):
        lut[tuple(currentPalleteColor)] = index
    
    lutColorDictionary = {
        0: "White", 1: "Off-White", 2: "Silver", 3: "Gray", 4: "Dark Gray",
        5: "Black", 6: "Lite Pink", 7: "More Pink", 8: "Hot Pink", 9: "Lipstick Red 1",
        10: "Red", 11: "Dark Red", 12: "Dark Tan", 13: "Tangerine", 14: "Light Brown",
        15: "Coffee", 16: "Light Tan", 17: "Light Yellow", 18: "Mustard Yellow", 19: "Lime",
        20: "Green", 21: "Green Bean", 22: "Camo Green 1", 23: "Cloud Blue    ", 24: "Robin Egg Blue",
        25: "Medium Blue 1", 26: "Blue", 27: "Bluejean", 28: "Lavener", 29: "Eggplant",
        30: "Ugly Purple?", 31: "Purple-Red Mix", 32: "Lipstick Red 2", 33: "Trump Tan", 34: "Caution Yellow",
        35: "Purple (Brown)", 36: "Chocholate", 37: "Milk Chocholate", 38: "Orange", 39: "Lapis Lazuli",
        40: "TheBlueCorner", 41: "Medium Blue 2", 42: "Turquoise", 43: "Purple-Black 1", 44: "Purple-Black 2",
        45: "Dark Purple", 46: "Purple", 47: "Light Purple", 48: "Dark Green", 49: "Camo Green 2",
        50: "Grass Green 1", 51: "Grass Green 2", 52: "Light Green"
    }

    print(f"#{taskNumber} Loading canvas")
    
    # Call and load the images
    bigCanvasImage = np.array(image)
    bigCanvasImage = cv2.cvtColor(bigCanvasImage, cv2.COLOR_RGB2BGR)
    canvasImage = convert_to_indexed(bigCanvasImage, lut) # Shrink it using the LUT
    
    canvasImage = np.uint8(canvasImage)

    for currentColor in searchable_colors_BGR:
        print(f"#{taskNumber} Swapping color to {currentColor}...")

        # Converts the current color to the LUT index
        currentColor = get_lut_index(lut, currentColor)

        # Creates a (1 channel) mask where all matching current colors are black and non-matching are white
        canvasImage_BW = cv2.inRange(canvasImage, currentColor, currentColor)

        swastikas = zip(swastikas_swas, swastikas_name)
        swastasks = []
        for swastika, swastika_name in swastikas:
            print(f"#{taskNumber} swapping swastika to {swastika_name}...")
            swastika = convert_to_indexed(swastika, lut) # Convert the swastika template using the LUT

            # If the template is larger than the megachunk, we just ignore the megachunk
            if swastika.shape[0] < canvasImage.shape[0] and swastika.shape[1] < canvasImage.shape[1]:

                # Stores all matches of all confidences of the black and white swastika to the black (which is actually the current color) and white (which is actually any other color) canvas
                matchTemplateResult = cv2.matchTemplate(canvasImage_BW, swastika, cv2.TM_CCOEFF_NORMED)

                # Debuging matching
                #if matchTemplateResult is not None:
                #    print(f'{swastika_name}: There are {len(np.where(matchTemplateResult >= -1)[0])} matches of any confidence')

                threshold = 1
                swastikaLocations = np.where(matchTemplateResult >= threshold)
                print(f"#{taskNumber} writting...")
                for X_Y_Pair in zip(*swastikaLocations[::-1]):
                    swastika_X, swastika_Y = X_Y_Pair # X & Y relative to the megachunk
                    #cv2.imshow('Image', cv2.resize(canvasImage[swastika_Y-1:swastika_Y + 6, swastika_X-1:swastika_X + 6], (500, 500), interpolation=cv2.INTER_NEAREST))
                    #cv2.waitKey(0)
                    #cv2.destroyAllWindows()
                    #print(f"{lutColorDictionary[currentColor]} - https://pixmap.fun/#{canvas_id},{swastika_X},{swastika_Y},36")
                    detectedName = f"{lutColorDictionary[currentColor]} {swastika_name}"
                    async with file_lock:
                        with open("swastikaList.txt", "a") as f:
                            f.write(f"{detectedName:<{display_length}} - https://pixmap.fun/#{canvas_id},{swastika_X + x},{swastika_Y + y},36\n")

# Function to process the image in chunks of 2000 pixels
async def process_image_in_chunks(canvas_id, canvas, start_x, start_y, image_width, image_height, start_date, end_date, chunk_size, queue):
    tasks = []
    swastikas_swas = []
    swastikas_name = []
    longest_name = 0
    taskNumber = 0

    semaphore = asyncio.Semaphore(4)
    async def semaphoreMegaChunkProcessor(canvas_id, canvas, x, y, chunk_width, chunk_height, start_date, end_date, taskNumber, searchable_colors_BGR, swastikas_swas, swastikas_name, display_length, batch_size, queue):
        async with semaphore:
            return await fetch_megachunk(canvas_id, canvas, x, y, chunk_width, chunk_height, start_date, end_date, taskNumber, searchable_colors_BGR, swastikas_swas, swastikas_name, display_length, batch_size, queue)

    # (Swastika) colors to look for
    searchable_colors_RGB = [
        # White to Black
        [255, 255, 255], [228, 228, 228], [196, 196, 196], [136, 136, 136], [78, 78, 78], [0, 0, 0],
        # Pink to Red
        [244, 179, 174], [255, 167, 209], [255, 84, 178], [255, 101, 101], [229, 0, 0], [154, 0, 0],
        # Orange to Brown
        [254, 164, 96], [229, 149, 0], [160, 106, 66], [96, 64, 40],
        # Tan to Yellow
        [245, 223, 176], [255, 248, 137], [229, 217, 0],
        # Light Green to Dark Green
        [148, 224, 68], [2, 190, 1], [104, 131, 56], [0, 101, 19],
        # Light Blue to Dark Blue
        [202, 227, 255], [0, 211, 221], [0, 131, 199], [0, 0, 234], [25, 25, 115],
        # Lavender to (Purple to) Light Red
        [207, 110, 228], [130, 0, 128], [83, 39, 68], [125, 46, 78], [193, 55, 71],
        # Orange to Orange
        [214, 113, 55], [252, 154, 41],
        # Dark Purple to Orange
        [68, 33, 57], [131, 51, 33], [163, 61, 24], [223, 96, 22],
        # Dark Blue to Light Blue
        [31, 37, 127], [10, 79, 175], [10, 126, 230], [88, 237, 240],
        # Dark Purple to Lavander
        [37, 20, 51], [53, 33, 67], [66, 21, 100], [74, 27, 144], [110, 75, 237],
        # Dark Green to Lime
        [16, 58, 47], [16, 74, 31], [16, 142, 47], [16, 180, 47], [117, 215, 87]
    ]

    # Converts the RGB array to a BGR array
    searchable_colors_BGR = [np.array(color[::-1], dtype=np.uint8) for color in searchable_colors_RGB]

    # Finds and loads all templates as BGR images
    rePattern = re.compile(r's.*_.*\.(png|jpe?g)', re.IGNORECASE)
    for filename in os.listdir('./templates'):
        if rePattern.fullmatch(filename):
            tempImg = cv2.imread(f'./templates/{filename}')
            if tempImg is not None:
                swastikas_swas.append(tempImg)

                swasName = filename.split('_', 1)[1].replace('.png', '')
                swastikas_name.append(swasName)
                if longest_name < len(swasName):
                    longest_name = len(swasName)
            del tempImg
    display_length = 16 + longest_name

    batch_size = 4
    
    # Chunk dimensions: Calculate how many chunks we need based on the image dimensions
    for y in range(start_y, image_height, chunk_size):
        for x in range(start_x, image_width, chunk_size):
            taskNumber += 1
            # Calculate the current chunk's width and height
            chunk_width = min(chunk_size, image_width - x)  # Avoid going beyond the image width
            chunk_height = min(chunk_size, image_height - y)  # Avoid going beyond the image height

            # Call the async get_area function for the current chunk
            tasks.append(asyncio.create_task(semaphoreMegaChunkProcessor(canvas_id, canvas, x, y, chunk_width, chunk_height, start_date, end_date, taskNumber, searchable_colors_BGR, swastikas_swas, swastikas_name, display_length, batch_size, queue)))
    
    total_timer_start = time.time()
    processedChunks = 0
    
    await asyncio.gather(*tasks)

    processedChunks = len(tasks)
    
    total_timer_end = time.time()
    total_time = total_timer_end - total_timer_start
    print(f"Processed all {processedChunks} mega-chunks ({processedChunks*10*(chunk_size/256):.0f} chunks) in {(total_time / 60):.0f} minutes and {(total_time % 60):02.0f} seconds")
    print("All swastikas have been saved to \"swastikaList.txt\"")
    print(f"-----  Here are the swastikas found  -----")

    with open("swastikaList.txt", "r") as file:
        for line in file:
            print(line, end="")  # end="" prevents double newlines
            
# Worker that just prints queue item size (for testing)
def queue_reader(queue):
    while True:
        item = queue.get()
        if item is None:
            break
        print(f"Received mega chunk")

def main():
    apime = fetchMe()

    if len(sys.argv) != 2 and len(sys.argv) != 2:
        print("Find all perfect swastikas across the canvas")
        print("")
        print("Usage:    naziFinder.py canvasID")
        print("")
        print("→Canvas is last obtainable history canvas. This is NOT the current canvas but close enough")
        print("→images will be saved into canvas folder")
        print("canvasID: ", end='')
        for canvas_id, canvas in apime['canvases'].items():
            if 'v' in canvas and canvas['v']:
                continue
            print(f"{canvas_id} = {canvas['title']}", end=', ')
        print()
        print("-----------")
        print("The coords will be output in terminal")
        return

    canvas_id = sys.argv[1]

    if canvas_id not in apime['canvases']:
        print("Invalid canvas selected")
        return

    canvas = apime['canvases'][canvas_id]

    if 'v' in canvas and canvas['v']:
        print("Can\'t get area for 3D canvas")
        return

    start = [0, 0] #[-32768, -32768] # Hard coded to full canvas
    end = [10239, 10239]#[32767, 32767] # Hard coded to full canvas
    start_date = datetime.date.today()
    end_date = datetime.date.today()
    x = int(start[0])
    y = int(start[1])
    w = int(end[0]) - x + 1
    h = int( end[1]) - y + 1
    if not os.path.exists('./templates'):
        os.mkdir('./templates')

    with open("swastikaList.txt", 'w') as file:
        pass

    #clear_screen()
    
    queue = Queue()

    # Start a simple reader process for testing
    reader = Process(target=queue_reader, args=(queue,))
    reader.start()

    # Fetch chunks and fill queue
    asyncio.run(process_image_in_chunks(canvas_id, canvas, x, y, w, h, start_date, end_date, 2560, queue))

    # Signal reader to stop
    queue.put(None)
    reader.join()
    print("-----  Done!  -----")

if __name__ == "__main__":
    main()
