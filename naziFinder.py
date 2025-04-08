#!/usr/bin/python3

import PIL.Image
import sys, io, os
import datetime
import asyncio
import aiohttp
import cv2
import numpy as np

USER_AGENT = "pmfun naziFinder 0.1.1 " + ' '.join(sys.argv[1:])
PPFUN_URL = "https://pixmap.fun"
PPFUN_STORAGE_URL = "https://backup.pixmap.fun"

# how many frames to skip
#  1 means none
#  2 means that every second frame gets captured
#  3 means every third
#  [...]
frameskip = 1

# Fetches the user data to use
async def fetchMe():
    url = f"{PPFUN_URL}/api/me"
    headers = {
      'User-Agent': USER_AGENT
    }
    async with aiohttp.ClientSession() as session:
        attempts = 0
        while True:
            try:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    return data
            except:
                if attempts > 3:
                    print(f"Could not get {url} in three tries, cancelling")
                    raise
                attempts += 1
                print(f"Failed to load {url}, trying again in 5s")
                await asyncio.sleep(5)
                pass
            
# Actually gets the chunk/image
async def fetch(session, url, offx, offy, image, bkg, needed = False):
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

# Gets the canvas
async def get_area(canvas_id, canvas, x, y, w, h, start_date, end_date):
    canvas_size = canvas["size"]
    bkg = tuple(canvas['colors'][0])

    delta = datetime.timedelta(days=1)
    end_date = end_date.strftime("%Y%m%d")
    iter_date = None
    cnt = 0
    #frames = []
    previous_day = PIL.Image.new('RGB', (w, h), color=bkg)
    while iter_date != end_date:
        iter_date = start_date.strftime("%Y%m%d")
        print('------------------------------------------------')
        print('Getting frames for date %s' % (iter_date))
        start_date = start_date + delta

        fetch_canvas_size = canvas_size
        if 'historicalSizes' in canvas:
            for ts in canvas['historicalSizes']:
                date = ts[0]
                size = ts[1]
                if iter_date <= date:
                    fetch_canvas_size = size

        # Calculates the chunk to get
        offset = int(-fetch_canvas_size / 2)
        xc = (x - offset) // 256
        wc = (x + w - offset) // 256
        yc = (y - offset) // 256
        hc = (y + h - offset) // 256
        print("Load from %s / %s to %s / %s with canvas size %s" % (xc, yc, wc + 1, hc + 1, fetch_canvas_size))

        # Calls and loads the chunk
        tasks = []
        async with aiohttp.ClientSession() as session:
            image = PIL.Image.new('RGBA', (w, h))
            for iy in range(yc, hc + 1):
                for ix in range(xc, wc + 1):
                    url = '%s/%s/%s/%s/%s/tiles/%s/%s.png' % (PPFUN_STORAGE_URL, iter_date[0:4], iter_date[4:6] , iter_date[6:], canvas_id, ix, iy)
                    offx = ix * 256 + offset - x
                    offy = iy * 256 + offset - y
                    tasks.append(fetch(session, url, offx, offy, image, bkg, True))
            await asyncio.gather(*tasks)
            print('Got start of day')
            # check if image is all just one color to lazily detect if whole full backup was 404
            clr = image.getcolors(1)
            if clr is not None:
                print("Got faulty full-backup frame, using last frame from previous day instead.")
                image = previous_day.copy()
            cnt += 1
            #frames.append(image.copy())
            image.save('./canvas/t%s.png' % (cnt))
            headers = {
                'User-Agent': USER_AGENT
            }
            while True:
                async with session.get('%s/history?day=%s&id=%s' % (PPFUN_URL, iter_date, canvas_id), headers=headers) as resp:
                    try:
                        time_list = await resp.json()
                        time_list = time_list[-1:] # Truncate to last element
                        break
                    except:
                        print('Couldn\'t decode json for day %s, trying again' % (iter_date))
            i = 0
            for time in time_list:
                i += 1
                if (i % frameskip) != 0:
                    continue
                if time == '0000':
                    # 0000 incremential backups are faulty
                    continue
                tasks = []
                image_rel = image.copy()
                for iy in range(yc, hc + 1):
                    for ix in range(xc, wc + 1):
                        url = '%s/%s/%s/%s/%s/%s/%s/%s.png' % (PPFUN_STORAGE_URL, iter_date[0:4], iter_date[4:6] , iter_date[6:], canvas_id, time, ix, iy)
                        offx = ix * 256 + offset - x
                        offy = iy * 256 + offset - y
                        tasks.append(fetch(session, url, offx, offy, image_rel, bkg))
                await asyncio.gather(*tasks)
                print('Got time %s' % (time))
                cnt += 1
                #frames.append(image.copy())
                image_rel.save('./canvas/t%s.png' % (cnt)) # t2 saved here

                # Call and load the images
                canvasImage = cv2.imread('./canvas/t%s.png' % (cnt))
                swastika = cv2.imread('./canvas/swastika.png')

                # Retrieve and store the height and width of the swastika
                swastika_height, swastika_width, _ = swastika.shape

                # (Swastika) colors to look for
                searchable_colors = [
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

                # Define the primaty and background colors of the template swastika
                primary_color = [0, 0, 0]
                background_color = [255, 255, 255]

                # Split the RGB channels
                canvasImage_BGR = cv2.split(canvasImage)
                swastika_BGR = cv2.split(swastika)

                result = None # Declare result as None

                for currentColor in searchable_colors:

                    # Creates a copy of the swastika template for colorshifting
                    colorShiftSwastika = swastika.copy()

                    # Creates a mask to find all black pixels in swastika template
                    mask_primary = np.all(colorShiftSwastika == primary_color, axis=-1)

                    # Replaces all black with the current color to search for
                    colorShiftSwastika[mask_primary] = currentColor

                    # Split the RGB channels
                    colorShiftSwastika_BGR = cv2.split(colorShiftSwastika)

                    greyscaleS = swastika.copy()
                    greyscaleS = np.uint8(greyscaleS)
                    #print(np.unique(greyscaleS))
                    #greyscaleS = np.ones_like(swastika, dtype=np.uint8)
                    greyscaleS = cv2.cvtColor(greyscaleS, cv2.COLOR_BGR2GRAY)
                    _, mask_background = cv2.threshold(greyscaleS, 240, 255, cv2.THRESH_BINARY_INV)
                    
                    #mask_background = np.ones_like(swastika, dtype=np.uint8)

                    mask_background = np.uint8(mask_background)

                    mask_background = np.array([
                        [  0,  0,  0,  0,  0,  0,  0],
                        [  0,255,  0,255,255,255,  0],
                        [  0,255,255,255,  0,  0,  0],
                        [  0,255,255,  0,255,255,  0],
                        [  0,  0,  0,255,  0,255,  0],
                        [  0,255,255,255,  0,255,  0],
                        [  0,  0,  0,  0,  0,  0,  0]], dtype=np.uint8)

                    #mask_background = np.array([
                    #    [255,255,255,255,255,255,255],
                    #    [255,  0,255,  0,  0,  0,255],
                    #    [255,  0,255,  0,255,255,255],
                    #    [255,  0,  0,255,  0,  0,255],
                    #    [255,255,255,  0,255,  0,255],
                    #    [255,  0,  0,  0,255,  0,255],
                    #    [255,255,255,255,255,255,255]], dtype=np.uint8)

                    print(mask_background)

                    #print(f"Template size: {swastika.shape}")
                    #print(f"Mask size: {mask_background.shape}")

                    

                    #tempImage = mask_background.copy()
                    #tempImage = cv2.resize(tempImage, (800, 800))
                    #cv2.imshow("Image", tempImage)
                    #cv2.waitKey(0)
                    #cv2.destroyAllWindows()

                    for canvasImage_channel, colorShiftSwastika_channel in zip(canvasImage_BGR, swastika_BGR):
                        match = cv2.matchTemplate(canvasImage_channel, colorShiftSwastika_channel, cv2.TM_CCOEFF_NORMED, mask=mask_background)
                        #print(match)
                        if result is None:
                            result = match
                        else:
                            result = cv2.min(result, match)

                    numResults = np.where(result >= -1)

                    #print(result)
                
                    if result is not None:
                        print(f'There are {len(numResults[0])} matches')

                    # Threshold and coordinate retrival
                    threshold = 0.9
                    swastikaLocations = np.where(result >= threshold)

                    print(f"------------------------------------------------\nSwastikas of color '{currentColor}' found:")
                    if len(swastikaLocations[0]) == 0:
                        print("No swastikas found")
                
                    for pt in zip(*swastikaLocations[::-1]):
                        sx, sy = pt # Extract (s)wastika (x) coordinate and (s)wastika (y) coordinates from coordinate pair
                        roi = canvasImage[sy:sy + swastika_height, sx:sx + swastika_width]

                        # Checks to make sure that the primary color matches the current colorshift
                        primary_color_match = np.all(roi[mask_primary] == currentColor)

                        # Checks to make sure that the background color is any non-current color
                        background_color_match = np.all(roi[~mask_primary] != currentColor)

                        # If both checks above pass, then it is a 100% match
                        if primary_color_match and background_color_match:
                            print(f"https://pixmap.fun/#{canvas_id},{sx},{sy},36")
                

                if time == time_list[-1]:
                    # if last element of day, copy it to previous_day to reuse it when needed
                    # print("Remembering last frame of day.")
                    previous_day.close()
                    previous_day = image_rel.copy();
                image_rel.close()
            image.close()
    previous_day.close()


async def main():
    apime = await fetchMe()

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

    start = [0, 0] # [-32768, -32768] # Hard coded to full canvas
    end = [510, 510] #[32767, 32767] # Hard coded to full canvas
    start_date = datetime.date.today()
    end_date = datetime.date.today()
    x = int(start[0])
    y = int(start[1])
    w = int(end[0]) - x + 1
    h = int( end[1]) - y + 1
    if not os.path.exists('./canvas'):
        os.mkdir('./canvas')
    await get_area(canvas_id, canvas, x, y, w, h, start_date, end_date)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
