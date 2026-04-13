import config

# Prints to terminal only in debug mode
# Will print if in debug mode, or if "enabled" is "True"
def debug(*args, enabled = None, **kwargs):
  if ((enabled is None and config.DEBUGGING_ENABLED) or (enabled is True)):
    print(*args, **kwargs)
  return
