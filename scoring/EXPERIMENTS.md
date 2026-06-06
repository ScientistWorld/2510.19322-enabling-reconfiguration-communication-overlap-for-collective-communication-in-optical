# Experiment Overview

## fig5_rabenseifner_allreduce_8node

Tests whether the reproduced scheduler improves communication completion time on the paper's small illustrative collective communication workload under the same fixed optical resources and timing assumptions. The experiment exists to verify the headline mechanism in a setting with dynamic topology demands, non-negligible switching delay, and strict collective step ordering.

## scaled_rabenseifner_allreduce_16node_k4

Tests whether the same evaluation pipeline remains meaningful on a slightly larger collective communication workload with more optical planes and realistic base latency. This experiment is a reproducible smoke benchmark for future agents; it is not a paper-reported numeric target.
