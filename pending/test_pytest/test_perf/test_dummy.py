

def test_dummy(duration):
    with duration("5 iteration for loop"):
        for _ in range(5):
            pass

    with duration("500 iteration for loop"):
        for _ in range(500):
            pass

    with duration("50000 iteration for loop"):
        for _ in range(50000):
            pass
