import sys
import argparse

import config
from Wplace.startup import startup
from Wplace.producers import workers

# Setup for CLI flags
def parse_args():

  parser = argparse.ArgumentParser(
    prog = "main.py",
    description = "Scans the canvas for matching template images."
  )
  parser.add_argument("--canvas-dir", "-c", default = None, help = f"Canvas root directory (default: {config.CANVAS_DIRECTORY})")
  parser.add_argument("--output-file", "-o", default = None, help = f"Output file (default: {config.OUTPUT_FILE})")
  parser.add_argument("--cpoint-file", "-p", default = None, help = f"File to use when restarting (default: {config.CHECKPOINT_FILE})")
  parser.add_argument("--template-dir", "-t", default = None, help = f"Template root directory (default: {config.TEMPLATE_DIRECTORY})")
  parser.add_argument("--workers", "-w", default = None, type = int, help = f"Number of I/O workers (default: {config.WORKER_COUNT})")
  parser.add_argument("--batch-size", "-b", default = None, type = int, help = f"GPU batch size (default: {config.BATCH_SIZE})")
  parser.add_argument("--restart", "-r", default = None, type = bool, help = f"Should script should resume after a crash (default: {config.SHOULD_RESTART})")
  parser.add_argument("--test", "-T", action="store_true", help="Run in test mode")

  # If no flags were used...
  if len(sys.argv) == 1:
    # ...run the help command and then stop

    parser.print_help() # Runs the help command
    sys.exit(0) # Exit with "success"
  
  # Otherwise, return the arguments
  return parser.parse_args()

# Overrides the default variables with user-specified flags
def apply_args(args):

  # If the script is running in test mode...
  if args.test: 

    print("Running in test mode...")
    config.DEBUGGING_ENABLED = args.test
    return # All other flags should be ignored in test mode

  if args.canvas_dir is not None: config.CANVAS_DIRECTORY = args.canvas_dir
  if args.output_file is not None: config.OUTPUT_FILE = args.output_file
  if args.cpoint_file is not None: config.CHECKPOINT_FILE = args.cpoint_file
  if args.template_dir is not None: config.TEMPLATE_DIRECTORY = args.template_dir
  if args.workers is not None: config.WORKER_COUNT = args.workers
  if args.batch_size is not None: config.BATCH_SIZE = args.batch_size
  if args.restart is not None: config.SHOULD_RESTART = args.restart

if __name__ == "__main__":
  
  # Manages CLI flags, and overrides defaults with user-specified flags
  args = parse_args() # If no flags were used, the program exists on this line
  apply_args(args)

  # Runs the startup script
  all_paths, templates, queue, semaphore = startup()

  # Starts the workers/producers
  workers(all_paths, queue, semaphore)
  
