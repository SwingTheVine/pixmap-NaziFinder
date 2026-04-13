import os

""" Configuration file for the script.
  This contains the default variables.
  Arguments/flags must be executed AFTER this is imported,
    but BEFORE anything else runs.
"""

_SCRIPT_DIR = os.path.dirname(__file__) # Working directory parent folder

# Default variable declarations, for when the user specifies no preference
CANVAS_DIRECTORY   = os.path.join(_SCRIPT_DIR, "test-canvas") # Folder that contains the entire canvas
OUTPUT_FILE        = os.path.join(_SCRIPT_DIR, "output.txt") # Output file that has Wplace links
CHECKPOINT_FILE    = os.path.join(_SCRIPT_DIR, "checkpoint.txt") # Restart file
TEMPLATE_DIRECTORY = os.path.join(_SCRIPT_DIR, "templates") # Folder that contains templates
WORKER_COUNT       = 5 # Number of workers to spawn
BATCH_SIZE         = 80 # GPU batch size
SHOULD_RESTART     = False # Should the checkpoint file be used to restart where the script last left off?
DEBUGGING_ENABLED  = False # Is the script running in test mode?
MINIMUM_BYTE_SIZE  = 230 # Ignores any tile with a file size that is less than or equal to this value

# Default variable declarations, but the user can NOT specify changes
MAX_QUEUE_SIZE     = BATCH_SIZE * 2 # Semaphore limit
COLOR_PRIMARY      = (  0,   0,   0, 255) # Primary color as RGBA
COLOR_NONPRIMARY   = (255, 255, 255, 255) # Non-primary color as RGBA
INDEX_PRIMARY      = 64 # Sentinel index for primary pixels
INDEX_NONPRIMARY   = 65 # Sentinel index for non-primary pixels
INDEX_UNKNOWN      = 255 # Sentinel index for strange pixels (catch-all)