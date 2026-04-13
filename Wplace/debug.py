import config

# Prints to terminal only in debug mode
def debug(*args, **kwargs):
  if config.DEBUGGING_ENABLED:
    print(*args, **kwargs)
  return
