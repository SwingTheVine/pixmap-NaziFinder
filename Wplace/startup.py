import os
import numpy as np
import multiprocessing as mp
from multiprocessing import Semaphore, Queue
from PIL import Image

import config
from debug import debug

minimum_pixels = 10^6 # Minimum number of pixels possible across all templates

# Converts one template to offsets
def load_template_offsets(template_path: str):

  img = Image.open(template_path).convert("RGBA") # Open the image as RGBA
  arr = np.array(img, dtype=np.uint8) # Convert the RGBA image to a Uint8 array
  H, W, _ = arr.shape # Get the height and width of the Uint8 array

  primary_offsets    = []
  nonprimary_offsets = []

  # For each row...
  for r in range(H):

    # For each column...
    for c in range(W):

      pixel = tuple(arr[r, c]) # Create a tuplet of this row/column position

      # If the pixel is a primary color, we add it to the primary offset array
      if pixel == config.COLOR_PRIMARY:
        primary_offsets.append((r, c))
      elif pixel == config.COLOR_NONPRIMARY:
        # Else, if the pixel is a non-primary color, we add it to the non-primary offset array
        nonprimary_offsets.append((r, c))

  # Returns the offset arrays
  return primary_offsets, nonprimary_offsets

# Collects all canvas PNG file absolute paths
def collect_paths(root_dir: str) -> list[str]:

  paths = []

  # For each file directory...
  for dirpath, _, filenames in os.walk(root_dir):
    # For each file in the file directory...
    for filename in filenames:
      # If the file is a PNG...
      if filename.lower().endswith(".png"):
        paths.append(os.path.join(dirpath, filename)) # Add the file to the paths array

  # Return the PNG files found.
  # The array is sorted to ensure consistancy between script restarts
  return sorted(paths)

# Loads checkpoint information
# This will return an integer that represents the number of canvas images processed
# This will stop working properly if the number of canvas images has changed since the crash
def load_checkpoint() -> int:
  # If the checkpoint file exists...
  if os.path.exists(config.CHECKPOINT_FILE):
    with open(config.CHECKPOINT_FILE, "r") as f: # Open the file...
      return int(f.read().strip()) # ...and return an integer
  return 0 # Else, return zero

# Startup sequence
def startup():

  debug("Begin of startup sequence...")

  print("Starting...")

  debug("├┬ 1/4 Collecting canvas images...")

  # Collects the canvas images
  all_paths = collect_paths(config.CANVAS_DIRECTORY)

  # If the program is resuming after a restart...
  if config.SHOULD_RESTART:

    # Loads checkpoint information
    resume_index = load_checkpoint()

    # If the index to resume at is a truthy value...
    if resume_index:
      print(f"│├─ Resuming from index {resume_index}.")
      all_paths = all_paths[resume_index:] # Trims the array to start at the resume index
  
  print(f"│├─ {len(all_paths)} tiles to process.")

  debug("│└─ Done!")
  debug("├┬ 2/4 Loading template offsets...")

  templates = []

  # For each template file in the template directory...
  for template_file in sorted(os.listdir(config.TEMPLATE_DIRECTORY)):

    # If the template is a PNG file...
    if template_file.lower().endswith(".png"):

      # Create an absolute path to the template file
      path = os.path.join(config.TEMPLATE_DIRECTORY, template_file)

      # Load the template offsets for that template
      primary_offsets, nonprimary_offsets = load_template_offsets(path)
      templates.append((primary_offsets, nonprimary_offsets))
      debug(f"│├─ {template_file}: {len(primary_offsets)} primary, {len(nonprimary_offsets)} non-primary pixels")

      # Minimum pixel variable will contain the smallest
      if len(primary_offsets): minimum_pixels = min(len(primary_offsets), minimum_pixels)
      if len(nonprimary_offsets): minimum_pixels = min(len(nonprimary_offsets), minimum_pixels)
  
  debug("│└─ Done!")
  debug("├┬ 3/4 Loading queue...")

  queue = Queue()

  debug("│└─ Done!")
  debug("├┬ 4/4 Loading semaphore...")

  semaphore = Semaphore(config.MAX_QUEUE_SIZE)

  debug(f"│├─ Bound semaphore to queue with size of {config.MAX_QUEUE_SIZE}. Batch size: {config.BATCH_SIZE}")
  debug("│└─ Done!")

  print("└─ Startup complete!")
  return all_paths, templates, queue, semaphore, minimum_pixels
