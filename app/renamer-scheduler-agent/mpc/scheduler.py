import syft as sy
import numpy as np

# Setup a local duet domain for each party
# In production, these would be run on different machines/users
# mpc/scheduler.py

def secure_bitmask_intersection(bitmasks):
    # Simulate secure intersection (logical AND)
    length = len(bitmasks[0])
    intersection = [1] * length
    for mask in bitmasks:
        for i in range(length):
            intersection[i] = intersection[i] & mask[i]
    return intersection

