import os
import cupy
import math
import time
import traceback
import numpy as np

import config
from debug import debug as _debug

_debugging_enabled = False

# The sight of spaghetti code makes your stomach grumble.
# You are filled with DETERMINATION.
def save_checkpoint(index: int):

  # Absolute file path for checkpoint temp file
  temp_file = config.CHECKPOINT_FILE + ".tmp"

  # Writes to the temp file
  with open(temp_file, "w") as file: # Opens the file
    file.write(str(index))
    file.flush()
    os.fsync(file.fileno())
  
  # Overrides the checkpoint file with the contents of the temp file
  os.replace(temp_file, config.CHECKPOINT_FILE)

# Appends a match to the output file
def write_match(output_file, tile_path: str, pixel_y: int, pixel_x: int):
  
  tile_x = int(os.path.basename(os.path.dirname(tile_path)))
  tile_y = int(os.path.splitext(os.path.basename(tile_path))[0])

  lat, lon = convert_coordinates(tile_x, tile_y, pixel_x, pixel_y)

  # Saves to the output file: tile/pixel coordinates, and a link to the match
  output_file.write(f"({tile_x:04d}, {tile_y:04d}, {pixel_x:03d}, {pixel_y:03d}) -- https://wplace.live/?lat={lat}&lng={lon}&zoom=16.15")
  output_file.flush()
  os.fsync(output_file.fileno())

# Converts tile/pixel coordinates to lat/long
def convert_coordinates(tile_x: int, tile_y: int, pixel_x: int, pixel_y: int):

  # Constants
  zoom = 11
  tile_size = 1000

  # Converts to pixel/pixel coordinates
  tile_x_fractional = tile_x + (pixel_x / tile_size)
  tile_y_fractional = tile_y + (pixel_y / tile_size)

  # Converts the pixel/pixel coordinates to percentage/percentage coordinates
  normalized = 2 ** zoom # Number of tiles per axis
  percentage_x = tile_x_fractional / normalized
  percentage_y = tile_y_fractional / normalized

  # Calculates the longitude
  lon = (percentage_x * 360) - 180

  # Calculates the latitude
  lat_rad = math.atan(math.sinh(math.pi * (1 - (2 * percentage_y))))
  lat = math.degrees(lat_rad)

  return lat, lon

# Scans a batch of images for any matching templates, using the GPU
def gpu_scan_batch(batch_cpu, templates):
  """
    batch_cpu: np.ndarray of shape (B, H, W), dtype uint8
    templates: list of (primary_offsets, nonprimary_offsets)
    Returns: list of (image_idx, row, col, template_idx) match tuples
  """

  # Retrieves the batch of images, as well as their height and width
  image_batch, image_height, image_width = batch_cpu.shape

  matches = [] # Stores any matches for this batch

  # Moves the batch images from the CPU to the GPU
  batch_gpu = cupy.asarray(batch_cpu) # RAM -> VRAM

  # For each template...
  for template_index, (primary_offsets, nonprimary_offsets) in enumerate(templates):
    
    # Get the template height/width
    template_height = max(row for row, column in primary_offsets + nonprimary_offsets) + 1
    template_width = max(column for row, column in primary_offsets + nonprimary_offsets) + 1
    
    # Get the farthest valid template coordinate
    operatable_height = image_height - template_height + 1
    operatable_width = image_width - template_width + 1

    # Converts all images in the batch into all possible "windows"
    # A "window" is a possible template location (e.g. 0/0, or 0/1, or 0/2, etc.)
    # Then, it "stacks" the windows along an axis (imagine them being vertically stacked like a tower)
    primary_slices = cupy.stack(
      [batch_gpu[:, row:row + operatable_height, column:column + operatable_width] for row, column in primary_offsets],
      axis = -1
    )

    first = primary_slices[:, :, :, 0:1] # Gets the primary color

    """ Imagine the tower from before.
      This takes the tower, and removes all non-primary pixels from it.
      Now you have a tower of windows, which only have primary pixels in them (non-square windows).
      Next, this will takes those primary pixels in each window, and shift them so they are a single row.
      Now, each window is a line of primary pixels, and each level of the tower is a window.
      Finally, this checks each window (row) and asks "is the entire row made of primary pixels?"
      If the answer is "yes", then that level of the tower is "True", otherwise "False"
     This means the tower is now functionally `Array<boolean>`. This is what "uniform" contains.
    """
    is_primary_window_uniform = cupy.all(primary_slices == first, axis=-1)

    # Records what the uniform result was for each window.
    # If the window exists normally, then it was uniform.
    # If the window failed the uniform check, then the window is "-1"
    C_map = first[:, :, :, 0].astype(cupy.int16)
    C_map[~is_primary_window_uniform] = -1

    # If nonprimary pixels are in the template
    if nonprimary_offsets:

      # (Read the comment for `primary_slices` first)
      # The function of this is similar.
      # However, we are now making a tower of only non-primary pixels.
      nonprimary_slices = cupy.stack(
        [batch_gpu[:, row:row + operatable_height, column:column + operatable_width] for row, column in nonprimary_offsets],
        axis = -1
      )
      has_no_nonprimary_conflict = cupy.all(
        nonprimary_slices != C_map[:, :, :, cupy.newaxis],
        axis = -1
      )
    else:
      # Else, the template does NOT contain non-primary pixels

      # Fill with "True"
      has_no_nonprimary_conflict = cupy.ones(
        (image_batch, operatable_height, operatable_width), dtype = bool
      )

    # Combines the two matches, so that only absolute matches remain
    is_valid_match = is_primary_window_uniform & has_no_nonprimary_conflict

    # Obtains every "True" value, which is every match
    hits_gpu = cupy.argwhere(is_valid_match)

    # Sends the matches to the CPU
    hits_cpu = cupy.asnumpy(hits_gpu)

    for image_index, row, column in hits_cpu:
      matches.append((int(image_index), int(row), int(column), template_index))

  return matches

# Takes a batch of images and sends them to the GPU for scanning.
# Also, writes any matches to the output file.
# Also, manages checkpoints.
def _flush_batch(batch_arrays, batch_paths, templates, output_file, batch_start_index):

  # Sticks each of the 80 images (which are arrays) into 1 Array
  batch_np = np.stack(batch_arrays, axis = 0)

  # Passes the images to the GPU, and scans them
  matches = gpu_scan_batch(batch_np, templates)

  # For each match...
  for image_index, match_row, match_column, template_index in matches:

    match_path = batch_paths[image_index] # Obtains the file path of the match

    debug(f"[gpu] Match: template={template_index} pos=({match_row}, {match_column}) file={match_path}")

    # Writes the match to the output file
    write_match(output_file, match_path, match_row, match_column)
  
  # Updates the checkpoint
  save_checkpoint(batch_start_index + len(batch_arrays))

# Debug wrapper
def debug(*args, **kwargs):
  global _debugging_enabled
  if _debugging_enabled:
    _debug(*args, enabled = _debugging_enabled, **kwargs)
  return

# Spawns the GPU thread, and starts scanning images
# Images only scan, provided there are a full batch of them, or a poison pill is observed
def gpu_thread(queue, semaphore, templates, total_images, debugging_enabled):

  print("[gpu] Spawning GPU thread...")

  global _debugging_enabled
  _debugging_enabled = debugging_enabled
  
  batch_arrays = []
  batch_paths = []
  batch_start_index = 0
  images_done = 0

  cupy.cuda.Device(config.GPU_INDEX).use()
  gpu_name = cupy.cuda.runtime.getDeviceProperties(cupy.cuda.Device().id)["name"].decode("utf-8")
  debug(f"[gpu] Thread using GPU device '{gpu_name}'")

  # Opens the output file
  output_file = open(config.OUTPUT_FILE, "a", buffering=1)
  print(f"[gpu] Ready! Waiting for {config.BATCH_SIZE} available images.")

  try:

    while True:

      queue_item = queue.get() # Retrieves an item from the queue
      # If there are no items in the queue, the thread halts here

      # If the queue item is a poison pill...
      if queue_item is None:

        print("[gpu] GPU thread poisoned!")

        # If there are still items to scan
        if batch_arrays:

          print("[gpu] Completing one last image scan before death...")

          # Scans the images in the partial batch
          _flush_batch(batch_arrays, batch_paths, templates, output_file, batch_start_index)
      
        break # Exit the while-loop
      
      # At this point, any queue item is (probably) an image

      path, indexed = queue_item # Deconstruct the item

      # Free/consume an item so that the queue has open space for more images
      semaphore.release()

      # Adds the queue item to the batch
      batch_arrays.append(indexed)
      batch_paths.append(path)

      images_done += 1 # Increases the number of images done by 1
      images_done_percent = (images_done / total_images) * 100

      # Outputs 10% intervals, OR in test mode, every image
      statement_output = f"[gpu] Buffered {images_done}/{total_images} images ({images_done_percent:.2f}%)"
      if ((int(images_done_percent) % 10) == 0):
        print(statement_output)
      else:
        debug(statement_output)
      
      debug(f"[gpu] Batch size now: {len(batch_arrays)}")

      # If the batch is full...
      if len(batch_arrays) == config.BATCH_SIZE:

        debug(f"[gpu] Scanning a batch of {len(batch_arrays)} images...")

        batch_time_start = time.perf_counter()
        
        # Scans the batch
        _flush_batch(batch_arrays, batch_paths, templates, output_file, batch_start_index)

        # Post-batch clean-up
        batch_start_index += config.BATCH_SIZE
        batch_arrays = []
        batch_paths = []

        batch_time_elapsed = time.perf_counter() - batch_time_start
        batch_time_hours, batch_time_remainder = divmod(batch_time_elapsed, 3600)
        batch_time_minutes, batch_time_seconds = divmod(batch_time_remainder, 60)
        debug(f"[gpu] Done scanning batch in {int(batch_time_hours):02d}:{int(batch_time_minutes):02d}:{batch_time_seconds:06.3f}.")
  
  except Exception as e:
    traceback.print_exc(file=output_file)
    raise # Rethrow the exception

  output_file.close() # Exits the output file
  
  print("[gpu] Killed.")
