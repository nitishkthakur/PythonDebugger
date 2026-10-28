import numpy as np
import pandas as pd

df = pd.DataFrame({"a": range(120), "b": np.linspace(0, 1, 120), "c": ["x", "y", "z"] * 40})
arr = np.arange(12).reshape(3, 4)
s = df["b"]
summary = df.groupby("c")["b"].mean()
print(summary)
