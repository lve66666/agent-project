import unittest

from fibonacci import first_n


class FirstNTest(unittest.TestCase):
    def test_count_zero(self):
        self.assertEqual(first_n(0), [])

    def test_count_one(self):
        self.assertEqual(first_n(1), [0])

    def test_count_two(self):
        self.assertEqual(first_n(2), [0, 1])

    def test_count_ten(self):
        result = first_n(10)
        self.assertEqual(len(result), 10)
        self.assertEqual(result, [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_count_one_hundred(self):
        result = first_n(100)
        self.assertEqual(len(result), 100)
        self.assertEqual(result[:2], [0, 1])
        self.assertEqual(result[9], 34)
        self.assertEqual(result[-1], 218922995834555169026)

    def test_negative_count(self):
        with self.assertRaises(ValueError):
            first_n(-1)


if __name__ == "__main__":
    unittest.main()
