# chart code
# will draw the CI bar and save it as an image

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')        #prevents the chart from trying to open a window
from ci_calculator import results, measurement_label

def generate_chart():        # pulling data from our CI calculator
    groups = list(results.keys())
    means = [results[g]["mean"] for g in groups]
    cis = [results[g]["ci"] for g in groups]

    #setting up the chart
    fig, ax = plt.subplots(figsize=(8, 5))

    #drawing bars
    colors = ["steelblue", "darkgreen"]
    bars = ax.bar(groups, means, color=colors, width=0.4,
                  yerr=cis, capsize=10, error_kw={"linewidth": 2,
                  "ecolor": "black", "capthick": 2})

    #Labels and title
    ax.set_title(f"95% Confidence comparison\n{measurement_label}",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel(measurement_label, fontsize=12)
    ax.set_xlabel("Treatment Group", fontsize=12)

    # adding mean values on top of each bar
    for bar, mean, ci in zip(bars, means, cis):
        ax.text(bar.get_x() + bar.get_width() / 2,
                mean + ci + 0.5,
                f"Mean: {mean}\n+-{ci}",
                ha="center", va="bottom", fontsize=10, fontweight="bold")

    # cleaning up the chart appearance
    ax.set_ylim(0, max(means) + max(cis) + 10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)

    plt.tight_layout()

    # saving the chart as an image inside the templates folder
    chart_path = "static/ci_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved to {chart_path}")

if __name__ == "__main__":
    generate_chart()



