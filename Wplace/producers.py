import os
import numpy as np
from multiprocessing import Pool
from multiprocessing import Value
from PIL import Image

import config
from debug import debug

_queue = None
_semaphore = None
_worker_id = None
_minimum_pixels = 10^6

_worker_counter = None # Static

# Runs once when the worker is spawned
# Obtains the queue and semaphore and binds them to local variables without making a copy
def _worker_init(queue, semaphore, counter, minimum_pixels):
  
  # Declares that these are class-variables, not local
  global _queue, _semaphore, _worker_id, _worker_counter, _minimum_pixels

  _queue = queue
  _semaphore = semaphore
  _minimum_pixels = minimum_pixels

  # Increments the worker ID every time a worker is spawned
  with counter.get_lock():
    _worker_id = counter.value
    counter.value += 1

# Runs once per image path
# This function holds the worker's work
def _worker_task(image_path):

  _semaphore.acquire() # Halts the worker if the queue is full
  # If this comment line is reached, the queue has space

  # If the template file size is too small, we skip it
  if os.path.getsize(image_path) <= config.MINIMUM_BYTE_SIZE:
    _semaphore.release() # Free/consume the image
    debug(f"[{_worker_id}] Skipped transparent tile ({parent}, {name})")
    return # Early-exit

  # Opens the image as RGBA
  image_RGBA = Image.open(image_path).convert("RGBA")

  # Converts the image to a Uint8 array
  image_array = np.array(image_RGBA, dtype = np.uint8)

  # Skip the tile if it is too transparent to contain a template
  if not is_worth_scanning(image_array):
    _semaphore.release() # Free/consume the image
    debug(f"[{_worker_id}] Skipped impossible tile ({parent}, {name})")
    return # Early-exit

  # Converts the Uint8 array to a LUT
  image_indexed = rgba_to_index(image_array)

  _queue.put((image_path, image_indexed)) # Adds the image to the queue

  parent = os.path.basename(os.path.dirname(image_path)) # Tile X
  name = os.path.splitext(os.path.basename(image_path))[0] # Tile Y
  
  debug(f"[{_worker_id}] Queued tile ({parent}, {name})")

# Converts the palette to a LUT
def rgba_to_index(arr: np.ndarray) -> np.ndarray:
  """ Converts (H, W, 4) uint8 RGBA arrays into (H, W) uint8 index array
    PRIMARY_COLOR    -> INDEX_PRIMARY    (64)
    NONPRIMARY_COLOR -> INDEX_NONPRIMARY (65)
    Everything else  -> INDEX_UNKNOWN    (255)
  """

  H, W, _ = arr.shape # Obtains the height and width of the array

  # Creates a new array that is the same size, but filled with INDEX_UNKNOWN LUT numbers (255)
  out = np.full((H, W), config.INDEX_UNKNOWN, dtype = np.uint8)

  # Creates a mask array where True means that pixel color
  # E.g. primary mask "True" is all primary color
  primary_mask = np.all(arr == config.PRIMARY_COLOR, axis = -1)
  nonprimary_mask = np.all(arr == config.NONPRIMARY_COLOR, axis = -1)

  # Overrides pixels in the new array with a mask over the old array.
  # E.g. All pixels that match on the mask will be brought over from the old array
  #      Everything else will be 255
  out[primary_mask] = config.INDEX_PRIMARY
  out[nonprimary_mask] = config.INDEX_NONPRIMARY

  return out # Returns the new array

# Does the image contain enough pixels for a template to exist?
def is_worth_scanning(image_array: np.ndarray) -> bool:
  
  alpha = image_array[:, :, 3] # Obtains the alpha

  opaque_pixels = np.count_nonzero(alpha) # Stores number of opaque pixels

  # Return true if the image contains AT LEAST enough pixels to match a template
  return opaque_pixels >= _minimum_pixels

# Spawns worker threads
def workers(all_paths, queue, semaphore, minimum_pixels):
  # Also kills the GPU thread

  print("Spawning workers...")
  debug(f"Workers IDs are 0-{config.WORKER_COUNT - 1}")

  counter = Value("i", 0) # Shares this (i)nteger across all workers

  # Starts the worker pool
  with Pool(
    processes = config.WORKER_COUNT,
    initializer = _worker_init,
    initargs = (queue, semaphore, counter, minimum_pixels)
  ) as pool:
    pool.map(_worker_task, all_paths)
  # The code will halt here until all canvas tiles are put in the queue

  print("Killing GPU thread...")

  # Poisons the queue
  queue.put(None)
