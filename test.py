
def turn_deltas_to_sequences(legal_deltas, rotations):
    sequences = []
    sequence_start = ["UP"] * rotations

    for delta in legal_deltas:
        if delta == 0:
            sequences.append(sequence_start + ["CONTINUE"])
            continue

        direction = "LEFT" if delta < 0 else "RIGHT"
        sequence = sequence_start + ([direction] * abs(delta))
        sequences.append(sequence)

    return sequences

ds = [-2, -1, 0, 1, 2, 3]
rotations = 3

print turn_deltas_to_sequences(ds, rotations)
