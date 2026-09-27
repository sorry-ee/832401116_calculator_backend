import unittest

from server import ExpressionError, calculate


class CalculatorTest(unittest.TestCase):
    def test_required_expressions(self):
        cases = {
            "1+2*3": 7,
            "(1+2)*3": 9,
            "10/2+7": 12,
            "8-3*2": 2,
            "-5+8": 3,
            "3*-2": -6,
            "1.5+2.25": 3.75,
            "sqrt(16)+2^3": 12,
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression), expected)

    def test_invalid_expressions(self):
        for expression in ("1/0", "1++", "(1+2", "abc", "sqrt(-1)"):
            with self.subTest(expression=expression):
                with self.assertRaises(ExpressionError):
                    calculate(expression)


if __name__ == "__main__":
    unittest.main()
