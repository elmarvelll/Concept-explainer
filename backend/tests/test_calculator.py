import pytest

from ai.calculator import CalculatorError, evaluate


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 + 2", 4),
        ("10 * 5", 50),
        ("100 / 4", 25),
        ("2 ** 5", 32),
        ("(10 + 5) * 2", 30),
        ("3.5 + 1.5", 5),
        ("-4 + 10", 6),
        ("15%", 0.15),
        ("15% * 200", 30),
        ("50% + 0.25", 0.75),
        ("7 % 3", 1),
        ("9 // 2", 4),
        ("2 ++ 2", 4),  # valid Python: 2 + (+2)
    ],
)
def test_valid_expressions(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "   ",
        "2 +",
        "import os",
        "__import__('os')",
        "os.system('ls')",
        "[1, 2, 3]",
        "2 if True else 3",
        "1 / 0",
        "9 ** 99999",
    ],
)
def test_invalid_or_unsafe_expressions_raise(expression):
    with pytest.raises(CalculatorError):
        evaluate(expression)
