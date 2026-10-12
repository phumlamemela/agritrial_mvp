#ci_calculator
#calculates the mean and the 95% confidence interval for each treatment group

import numpy as np
from scipy import stats
from data import group_a, group_b, group_names, measurement_label

def calculate_ci(group):
    n = len(group)                       # number of samples
    mean = np.mean(group)                #average
    std_err = stats.sem(group)           # standard error of the mean
    ci = std_err * 1.96                  # 95% confidence interval margin
    return mean, ci

# calculating for both groups
mean_a, ci_a = calculate_ci(group_a)
mean_b, ci_b = calculate_ci(group_b)

# store results neatly
results = {
    group_names[0]: {"mean": round(mean_a, 2), "ci": round(ci_a, 2)},
    group_names[1]: {"mean": round(mean_b, 2), "ci": round(ci_b, 2)},
}

# printing results so we can see them
if __name__ == "__main__":
    print(f"\n=== CI Results for {measurement_label} ===")
    for group, values in results.items():
        print(f"{group}: Mean = {values['mean']} | 95% CI = +-{values['ci']}")