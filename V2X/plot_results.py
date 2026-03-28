import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# load results
df = pd.read_csv("results/baseline_message_events.csv")

# get delay values
delays = df["delay_ms"].dropna()

# sort values
sorted_delays = np.sort(delays)

# compute CDF
cdf = np.arange(len(sorted_delays)) / float(len(sorted_delays))

# plot
plt.figure(figsize=(6,4))
plt.plot(sorted_delays, cdf)

plt.xlabel("Delay (ms)")
plt.ylabel("CDF")
plt.title("CDF of V2X Message Delay")
plt.grid(True)

plt.savefig("delay_cdf.png", dpi=300)
plt.show()
