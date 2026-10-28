"""Class hierarchy demo for hover info (signature, file, MRO). Break on the `total = ...` line."""
import os


class Base:
    """Root of the hierarchy."""

    def greet(self, name: str, punctuation: str = "!") -> str:
        """Return a greeting."""
        return "hello " + name + punctuation


class Mixin:
    """Adds helpers; its greet() wins over Base.greet() in the MRO."""

    def helper(self, n: int) -> int:
        return n * 2

    def greet(self, name, punctuation="?"):
        return "mixin " + name


class Child(Mixin, Base):
    """A child with multiple inheritance."""

    def __init__(self, value):
        self.value = value

    @property
    def doubled(self):
        return self.value * 2

    @staticmethod
    def make(v):
        return Child(v)


def build(count: int, label: str = "x") -> list:
    """Build a list of children."""
    out = []
    for i in range(count):
        child = Child.make(i)
        out.append(child)
    return out


if __name__ == "__main__":
    kids = build(3)
    first = kids[0]
    text = first.greet("bob")
    path = os.path.join("a", "b")
    total = first.helper(first.value) + first.doubled
    print(text, path, total)
