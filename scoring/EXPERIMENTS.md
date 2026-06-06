# Experiment Overview

## fig5_rabenseifner_allreduce_8node

Tests whether the reproduced scheduler improves communication completion time on the paper's small illustrative collective communication workload under the same fixed optical resources and timing assumptions. The experiment exists to verify the headline mechanism in a setting with dynamic topology demands, non-negligible switching delay, and strict collective step ordering.

## fig8_rabenseifner_allreduce_64node_k4

Tests the same scheduling objective on a larger collective workload from the paper's scalability study. It checks whether the evaluation remains meaningful when there are more ordered communication stages and the fixed optical resources must support a broader sequence of topology demands.

## fig8_rabenseifner_allreduce_512node_k4

Tests the scalability target at a substantially larger node count while keeping the paper's fixed network resource assumptions. This gives future agents a harder setting than the illustrative example while preserving the same correctness requirements and benefit metric.
