import unittest

from calculator import divide


class CalculatorTests(unittest.TestCase):
    def test_divide_by_zero_has_helpful_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero"):
            divide(10, 0)


if __name__ == "__main__":
    unittest.main()
