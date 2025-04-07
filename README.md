# NaziFinder
This script finds all swastikas on pixmap.fun (or any canvas running the pixelplanet.fun software). **Not all detected swastikas are actually swastikas.** There *will* be false positives.

## I want to detect a different type of swastika/hate symbol
 You can change the design you are looking for by changing the design of the canvas/swastika.png file. The swastika template is 1-bit meaning the design should be black, and null/empty/background space is white. For example, if you change the design of canvas/swastika.png to be a black smiley face on a white background, it will attempt to detect the smiley face *as a pattern* on top of any random combination of pixels (that are a different color than the smiley face)