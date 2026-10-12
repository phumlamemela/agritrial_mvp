#data.py
# Sample trails data for our Agritrial MVP
#Simulates nitrate readings (mg/L) for two treatment groups

import numpy as np

#setting a seed so that random data is the same everytime I run it

np.random.seed(42)

# Treatment group A - Control (no biostimulant)
# 10 nitrate readings in mg/L
group_a = np.random.normal(loc=30, scale=5, size=10)

#Treatment Group B - Biostimulant applied
#10 nitrate readings in mg/L (higher average, showing the biostimulant worked)
group_b = np.random.normal(loc=45, scale=6, size=10)

#Label for measurement being compared
measurement_label = "Nitrate Level (mg/L)"

#Group names
group_names = ["Control (Group a)", "Biostimulant (Group B)"]