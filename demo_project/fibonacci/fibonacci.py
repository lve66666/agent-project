def first_n(count: int) -> list[int]:
    """返回斐波那契数列的前 count 项。

    斐波那契数列定义为：
        F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)

    参数：
        count: 要返回的项数，必须为非负整数。

    返回：
        斐波那契数列前 count 项组成的列表。

    异常：
        ValueError: 当 count 为负数时抛出。
    """
    if count < 0:
        raise ValueError("count must be non-negative")

    if count == 0:
        return []

    sequence = [0, 1]
    if count == 1:
        return sequence[:1]

    for _ in range(2, count):
        sequence.append(sequence[-1] + sequence[-2])

    return sequence
