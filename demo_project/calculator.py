def divide(left: float, right: float) -> float:
    """Return left divided by right."""
    if right == 0:
        raise ValueError("Cannot divide by zero")
    return left / right
