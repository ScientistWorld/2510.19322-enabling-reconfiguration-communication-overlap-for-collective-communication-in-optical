# Experiment Overview

## fig5_rabenseifner_allreduce_8node

Tests whether the reproduced scheduler improves communication completion time on the paper's small illustrative collective communication workload under the same fixed optical resources and timing assumptions. The experiment exists to verify the headline mechanism in a setting with dynamic topology demands, non-negligible switching delay, and strict collective step ordering.

## fig8_rabenseifner_allreduce_64node_k4

Tests the same scheduling objective on a larger collective workload from the paper's scalability study. It checks whether the evaluation remains meaningful when there are more ordered communication stages and the fixed optical resources must support a broader sequence of topology demands.

## fig8_rabenseifner_allreduce_512node_k4

Tests the scalability target at a substantially larger node count while keeping the paper's fixed network resource assumptions. This gives future agents a harder setting than the illustrative example while preserving the same correctness requirements and benefit metric.

## fig8_pairwise_alltoall_5node_k4

Tests the scalability target for a dense ordered exchange workload at the smaller node count reported in the paper. This target checks whether a candidate scheduler can improve completion time when every communication stage asks for a new topology and static reservation is capacity-limited.

## fig8_pairwise_alltoall_10node_k4

Tests the same dense ordered exchange workload at the larger reported node count. This target adds a second collective family to the benchmark and makes the evaluation less tied to the AllReduce traffic pattern.
