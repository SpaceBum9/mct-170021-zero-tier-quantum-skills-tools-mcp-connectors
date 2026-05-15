import math

def euclidean_sequence(start, end, step=1):
    """Generate Euclidean-distributed sequence using GCD spacing."""
    seq = []
    current = start
    while current <= end:
        seq.append(current)
        current += step
    # Balance with GCD
    gcd_val = math.gcd(int(step * 100), int((end - start) * 100))
    return [x for x in seq if (x - start) % (gcd_val or 1) == 0]

def normalize_to_universe(seq, scale_factor=1.0):
    """Mirror and scale sequence across uni-multiverse instances."""
    mirrored = [-x for x in seq]
    scaled = [x * scale_factor for x in seq]
    parallel = seq + mirrored + scaled
    return sorted(set(parallel))