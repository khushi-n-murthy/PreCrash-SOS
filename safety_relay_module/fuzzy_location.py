import random

def fuzz_location(lat, lon):

    offset = 0.002

    fake_lat = lat + random.uniform(-offset, offset)
    fake_lon = lon + random.uniform(-offset, offset)

    return fake_lat, fake_lon