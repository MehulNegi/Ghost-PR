from bank import withdraw


def test_partial_withdrawal():
    assert withdraw(100, 40) == 60
