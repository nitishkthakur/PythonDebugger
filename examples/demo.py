"""Demo target for debugger.py: functions, containers, enum, class, a bool bug."""
import enum
from dataclasses import dataclass


class Color(enum.Enum):
    RED = 1
    GREEN = 2


@dataclass
class Item:
    name: str
    price: float
    tags: list


def total(items, discount):
    s = 0.0
    for it in items:
        s += it.price
    s = s * (1 - discount)
    return s


def process(items):
    enabled = False          # bug: should be True
    result = {}
    for it in items:
        if enabled:
            result[it.name] = it.price
    return result, total(items, 0.1)


def main():
    items = [Item("apple", 1.5, ["fruit"]), Item("pear", 2.25, ["fruit", "green"]), Item("nut", 9.0, [])]
    colors = {Color.RED: "r", Color.GREEN: "g"}
    ids = {3, 1, 2}
    matrix = [[1, 2, 3], [4, 5, 6]]
    result, t = process(items)
    print("result:", result, "total:", t)
    print("sorted:", sorted(ids, key=lambda i: -i))
    return colors, matrix


if __name__ == "__main__":
    main()
    print("done")
