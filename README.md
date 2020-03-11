# maskTiff4Maud
Utility to prepare tiff files before loading data into the Rietveld refinement software MAUD

How does this work? MAUD ignores pixels with a -1 intensity. Hence, this software sets a -1 intensity value at all points that should be masked.

This program is written in python and should work on most platforms. Download maskTiff4Maud.py and run it with python. It is the only file you need.

How to proceed?

Create a mask, with Dioptas for instance, and save it,
- Load you data and your mask in MaskTiff4Maud,
- Check that the orientation of the mask is correct, otherwise, flip and rotate the mask until it works,
- Save your masked data in Tiff and proceed to process it with MAUD.

Good luck with your data!

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

The source code is available at https://github.com/smerkel/maskTiff4Maud. 
