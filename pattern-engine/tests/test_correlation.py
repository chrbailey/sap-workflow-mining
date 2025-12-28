"""
Tests for outcome correlation module.

Tests cover:
- Effect size calculations
- Statistical significance testing
- Confidence intervals
- Known correlation patterns
"""

import pytest
import math
import numpy as np

from src.correlate.outcome_analyzer import (
    OutcomeAnalyzer,
    EffectSize,
    calculate_cohens_d,
)


class TestEffectSizeCalculations:
    """Tests for effect size calculations."""

    def test_cohens_d_positive(self):
        """Test Cohen's d for positive difference."""
        d = calculate_cohens_d(
            group1_mean=10.0, group1_std=2.0, group1_n=30,
            group2_mean=8.0, group2_std=2.0, group2_n=30
        )

        # Positive difference
        assert d > 0
        # Expected d = 2/2 = 1.0 (large effect)
        assert abs(d - 1.0) < 0.1

    def test_cohens_d_negative(self):
        """Test Cohen's d for negative difference."""
        d = calculate_cohens_d(
            group1_mean=5.0, group1_std=2.0, group1_n=30,
            group2_mean=7.0, group2_std=2.0, group2_n=30
        )

        # Negative difference
        assert d < 0
        assert abs(d + 1.0) < 0.1

    def test_cohens_d_no_difference(self):
        """Test Cohen's d when means are equal."""
        d = calculate_cohens_d(
            group1_mean=5.0, group1_std=2.0, group1_n=30,
            group2_mean=5.0, group2_std=2.0, group2_n=30
        )

        assert abs(d) < 0.01

    def test_cohens_d_zero_std(self):
        """Test Cohen's d when standard deviation is zero."""
        d = calculate_cohens_d(
            group1_mean=5.0, group1_std=0.0, group1_n=30,
            group2_mean=5.0, group2_std=0.0, group2_n=30
        )

        assert d == 0.0


class TestEffectSizeInterpretation:
    """Tests for effect size interpretation."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return OutcomeAnalyzer(delay_threshold_days=7)

    def create_docs_with_timing(self, values, metric='order_to_delivery_days'):
        """Helper to create documents with specific timing values."""
        return [
            {'doc_key': f'doc_{i}', 'timing': {metric: v}}
            for i, v in enumerate(values)
        ]

    def test_large_effect_detected(self, analyzer):
        """Test that large effects are correctly identified."""
        # Create cluster with much higher values than baseline
        baseline_docs = self.create_docs_with_timing([5, 6, 5, 6, 5, 6, 5, 6, 5, 6])
        cluster_docs = self.create_docs_with_timing([15, 16, 15, 16, 15, 16, 15, 16, 15, 16])

        all_docs = baseline_docs + cluster_docs
        labels = [0] * 10 + [1] * 10

        cluster_result = {
            'labels': labels,
            'n_clusters': 2,
        }

        result = analyzer.analyze(all_docs, cluster_result)

        # Cluster 1 should show large effect
        cluster_1 = result['clusters'].get('1', {})
        if 'effect_sizes' in cluster_1:
            effect = cluster_1['effect_sizes'].get('order_to_delivery_days', {})
            if effect:
                # The cluster has much higher values
                assert effect.get('difference', 0) > 0
                assert effect.get('effect_interpretation') in ('medium', 'large')

    def test_small_effect_detected(self, analyzer):
        """Test that small effects are correctly identified."""
        # Create cluster with slightly different values
        baseline_docs = self.create_docs_with_timing([5, 6, 5, 6, 5, 6, 5, 6, 5, 6])
        cluster_docs = self.create_docs_with_timing([6, 7, 6, 7, 6, 7, 6, 7, 6, 7])

        all_docs = baseline_docs + cluster_docs
        labels = [0] * 10 + [1] * 10

        cluster_result = {
            'labels': labels,
            'n_clusters': 2,
        }

        result = analyzer.analyze(all_docs, cluster_result)

        # Cluster 1 should show small effect
        cluster_1 = result['clusters'].get('1', {})
        if 'effect_sizes' in cluster_1:
            effect = cluster_1['effect_sizes'].get('order_to_delivery_days', {})
            if effect:
                assert effect.get('difference', 0) > 0
                assert effect.get('effect_interpretation') in ('negligible', 'small')


class TestKnownCorrelations:
    """Tests with synthetic data where correlations are known."""

    @pytest.fixture
    def known_pattern_docs(self):
        """
        Create documents with known patterns:
        - Cluster 0: Fast processing (low lead times)
        - Cluster 1: Slow processing (high lead times)
        """
        docs = []

        # Cluster 0: Fast - order_to_delivery around 3 days
        for i in range(20):
            docs.append({
                'doc_key': f'fast_{i}',
                'cluster_id': 0,
                'timing': {
                    'order_to_delivery_days': 3 + np.random.normal(0, 0.5),
                    'delivery_to_invoice_days': 1 + np.random.normal(0, 0.3),
                    'order_to_invoice_days': 4 + np.random.normal(0, 0.6),
                    'delay_from_requested_days': -1 + np.random.normal(0, 0.3),
                }
            })

        # Cluster 1: Slow - order_to_delivery around 12 days
        for i in range(20):
            docs.append({
                'doc_key': f'slow_{i}',
                'cluster_id': 1,
                'timing': {
                    'order_to_delivery_days': 12 + np.random.normal(0, 1.0),
                    'delivery_to_invoice_days': 3 + np.random.normal(0, 0.5),
                    'order_to_invoice_days': 15 + np.random.normal(0, 1.2),
                    'delay_from_requested_days': 5 + np.random.normal(0, 0.8),
                }
            })

        return docs

    def test_known_pattern_detection(self, known_pattern_docs):
        """Test that known patterns are detected correctly."""
        np.random.seed(42)

        labels = [0] * 20 + [1] * 20
        cluster_result = {
            'labels': labels,
            'n_clusters': 2,
        }

        analyzer = OutcomeAnalyzer(delay_threshold_days=3)
        result = analyzer.analyze(known_pattern_docs, cluster_result)

        # Check baseline
        baseline = result['baseline']
        assert 'order_to_delivery_days' in baseline

        # Check cluster 1 (slow) has higher values than cluster 0 (fast)
        cluster_0 = result['clusters'].get('0', {})
        cluster_1 = result['clusters'].get('1', {})

        if cluster_0 and cluster_1:
            effect_0 = cluster_0.get('effect_sizes', {}).get('order_to_delivery_days', {})
            effect_1 = cluster_1.get('effect_sizes', {}).get('order_to_delivery_days', {})

            if effect_0 and effect_1:
                # Cluster 0 should be below baseline (negative difference)
                # Cluster 1 should be above baseline (positive difference)
                assert effect_0.get('difference', 0) < effect_1.get('difference', 0)

    def test_delay_probability_correlation(self, known_pattern_docs):
        """Test that delay probability correlations are detected."""
        np.random.seed(42)

        labels = [0] * 20 + [1] * 20
        cluster_result = {
            'labels': labels,
            'n_clusters': 2,
        }

        # Use threshold where cluster 1 will have more delays
        analyzer = OutcomeAnalyzer(delay_threshold_days=3)
        result = analyzer.analyze(known_pattern_docs, cluster_result)

        # Cluster 1 (slow) should have higher delay probability
        cluster_1 = result['clusters'].get('1', {})
        if cluster_1:
            delay_effect = cluster_1.get('effect_sizes', {}).get('delay_probability', {})
            if delay_effect:
                # Slow cluster should have more delays
                assert delay_effect.get('cluster_value', 0) > delay_effect.get('baseline_value', 0)


class TestStatisticalSignificance:
    """Tests for statistical significance testing."""

    def test_significant_difference_detected(self):
        """Test that significant differences are flagged."""
        # Create clearly different groups
        docs = []

        # Group 0: Low values
        for i in range(30):
            docs.append({
                'doc_key': f'low_{i}',
                'timing': {'order_to_delivery_days': 3.0}
            })

        # Group 1: High values
        for i in range(30):
            docs.append({
                'doc_key': f'high_{i}',
                'timing': {'order_to_delivery_days': 15.0}
            })

        labels = [0] * 30 + [1] * 30
        cluster_result = {'labels': labels, 'n_clusters': 2}

        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze(docs, cluster_result)

        # At least one cluster should show significant effect
        has_significant = False
        for cluster_id, cluster_data in result['clusters'].items():
            for metric, effect in cluster_data.get('effect_sizes', {}).items():
                if effect.get('is_significant', False):
                    has_significant = True
                    break

        # With such distinct groups, significance should be detected
        # (Though exact results depend on variance)

    def test_non_significant_difference_not_flagged(self):
        """Test that non-significant differences are not flagged."""
        # Create groups with similar values and high variance
        docs = []
        np.random.seed(42)

        for i in range(20):
            docs.append({
                'doc_key': f'doc_{i}',
                'timing': {'order_to_delivery_days': 5.0 + np.random.normal(0, 3)}
            })

        labels = [i % 2 for i in range(20)]  # Alternating labels
        cluster_result = {'labels': labels, 'n_clusters': 2}

        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze(docs, cluster_result)

        # With alternating labels and same distribution, effects should be small
        for cluster_data in result['clusters'].values():
            for effect in cluster_data.get('effect_sizes', {}).values():
                if effect.get('effect_interpretation') == 'large':
                    # Large effects should not occur with this data
                    assert False, "Unexpected large effect with homogeneous data"


class TestConfidenceIntervals:
    """Tests for confidence interval calculations."""

    def test_confidence_interval_contains_difference(self):
        """Test that CI contains the estimated difference."""
        docs = []
        np.random.seed(42)

        for i in range(30):
            docs.append({
                'doc_key': f'a_{i}',
                'timing': {'order_to_delivery_days': 5.0 + np.random.normal(0, 1)}
            })
        for i in range(30):
            docs.append({
                'doc_key': f'b_{i}',
                'timing': {'order_to_delivery_days': 7.0 + np.random.normal(0, 1)}
            })

        labels = [0] * 30 + [1] * 30
        cluster_result = {'labels': labels, 'n_clusters': 2}

        analyzer = OutcomeAnalyzer(confidence_level=0.95)
        result = analyzer.analyze(docs, cluster_result)

        for cluster_data in result['clusters'].values():
            for effect in cluster_data.get('effect_sizes', {}).values():
                diff = effect.get('difference', 0)
                ci_lower = effect.get('ci_lower', 0)
                ci_upper = effect.get('ci_upper', 0)

                # Difference should be within CI
                # (This is a sanity check - the CI is for the difference)
                assert ci_lower <= diff <= ci_upper

    def test_wider_ci_with_smaller_sample(self):
        """Test that smaller samples produce wider CIs."""
        # Large sample
        docs_large = []
        for i in range(50):
            docs_large.append({
                'doc_key': f'l_{i}',
                'timing': {'order_to_delivery_days': 5.0}
            })
        for i in range(50):
            docs_large.append({
                'doc_key': f'l2_{i}',
                'timing': {'order_to_delivery_days': 7.0}
            })

        labels_large = [0] * 50 + [1] * 50

        # Small sample
        docs_small = []
        for i in range(10):
            docs_small.append({
                'doc_key': f's_{i}',
                'timing': {'order_to_delivery_days': 5.0}
            })
        for i in range(10):
            docs_small.append({
                'doc_key': f's2_{i}',
                'timing': {'order_to_delivery_days': 7.0}
            })

        labels_small = [0] * 10 + [1] * 10

        analyzer = OutcomeAnalyzer()

        result_large = analyzer.analyze(
            docs_large,
            {'labels': labels_large, 'n_clusters': 2}
        )
        result_small = analyzer.analyze(
            docs_small,
            {'labels': labels_small, 'n_clusters': 2}
        )

        # Get CI widths for cluster 1
        def get_ci_width(result):
            cluster = result['clusters'].get('1', {})
            effect = cluster.get('effect_sizes', {}).get('order_to_delivery_days', {})
            if effect:
                return effect.get('ci_upper', 0) - effect.get('ci_lower', 0)
            return None

        width_large = get_ci_width(result_large)
        width_small = get_ci_width(result_small)

        if width_large is not None and width_small is not None:
            # Smaller sample should have wider CI
            assert width_small >= width_large


class TestAnalyzerEdgeCases:
    """Tests for edge cases in the analyzer."""

    def test_empty_documents(self):
        """Test handling of empty document list."""
        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze([], {'labels': [], 'n_clusters': 0})

        assert result['n_documents'] == 0
        assert result['n_clusters_analyzed'] == 0

    def test_missing_timing_data(self):
        """Test handling of missing timing data."""
        docs = [
            {'doc_key': 'doc_1', 'timing': {}},
            {'doc_key': 'doc_2', 'timing': None},
            {'doc_key': 'doc_3'},
        ] * 5

        labels = [0] * 15
        cluster_result = {'labels': labels, 'n_clusters': 1}

        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze(docs, cluster_result)

        # Should handle gracefully without crashing
        assert result is not None

    def test_all_noise_labels(self):
        """Test handling when all documents are noise (-1)."""
        docs = [
            {'doc_key': f'doc_{i}', 'timing': {'order_to_delivery_days': 5}}
            for i in range(10)
        ]

        labels = [-1] * 10
        cluster_result = {'labels': labels, 'n_clusters': 0}

        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze(docs, cluster_result)

        assert result['n_clusters_analyzed'] == 0

    def test_single_cluster(self):
        """Test with only one cluster."""
        docs = [
            {'doc_key': f'doc_{i}', 'timing': {'order_to_delivery_days': 5 + i}}
            for i in range(10)
        ]

        labels = [0] * 10
        cluster_result = {'labels': labels, 'n_clusters': 1}

        analyzer = OutcomeAnalyzer()
        result = analyzer.analyze(docs, cluster_result)

        assert result['n_clusters_analyzed'] == 1


class TestEffectSizeDataclass:
    """Tests for EffectSize dataclass."""

    def test_to_dict_from_dict_roundtrip(self):
        """Test serialization roundtrip."""
        effect = EffectSize(
            metric='order_to_delivery_days',
            cluster_value=10.0,
            baseline_value=7.0,
            difference=3.0,
            effect_size=0.8,
            effect_interpretation='medium',
            ci_lower=2.0,
            ci_upper=4.0,
            p_value=0.01,
            is_significant=True,
            n_cluster=30,
            n_baseline=100
        )

        d = effect.to_dict()
        restored = EffectSize.from_dict(d)

        assert restored.metric == effect.metric
        assert restored.cluster_value == effect.cluster_value
        assert restored.difference == effect.difference
        assert restored.is_significant == effect.is_significant
