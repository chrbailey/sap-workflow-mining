"""
Tests for predictive monitoring module.

Tests cover:
- Feature extraction from event traces
- Classification model training and prediction
- Regression model training and prediction
- Alert generation and management
- Predictive monitor orchestration
- Edge cases and error handling
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from src.prediction import (
    # Features
    FeatureExtractor,
    FeatureConfig,
    FeatureType,
    ExtractedFeatures,
    O2C_ACTIVITIES,
    O2C_MILESTONE_ORDER,
    extract_features,
    extract_features_batch,
    # Models
    ClassificationModel,
    RegressionModel,
    PredictiveModel,
    PredictiveMonitor,
    ModelConfig,
    ModelType,
    Prediction,
    PredictionType,
    TrainingResult,
    create_late_delivery_model,
    create_credit_hold_model,
    create_completion_time_model,
    # Alerts
    Alert,
    AlertConfig,
    AlertHandler,
    AlertManager,
    AlertSeverity,
    AlertThreshold,
    AlertType,
    CallbackAlertHandler,
    LoggingAlertHandler,
    QueueAlertHandler,
    RiskScorer,
    create_alert_manager,
)


class TestFeatureConfig:
    """Tests for FeatureConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FeatureConfig()

        assert config.include_temporal is True
        assert config.include_counts is True
        assert config.include_patterns is True
        assert config.include_state is True
        assert config.time_units == "hours"

    def test_custom_config(self):
        """Test custom configuration."""
        config = FeatureConfig(
            include_temporal=False,
            time_units="days",
            max_sequence_length=50
        )

        assert config.include_temporal is False
        assert config.time_units == "days"
        assert config.max_sequence_length == 50

    def test_time_divisor_hours(self):
        """Test time divisor for hours."""
        config = FeatureConfig(time_units="hours")

        assert config.get_time_divisor() == 3600.0

    def test_time_divisor_days(self):
        """Test time divisor for days."""
        config = FeatureConfig(time_units="days")

        assert config.get_time_divisor() == 86400.0

    def test_time_divisor_minutes(self):
        """Test time divisor for minutes."""
        config = FeatureConfig(time_units="minutes")

        assert config.get_time_divisor() == 60.0


class TestFeatureExtractor:
    """Tests for FeatureExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a feature extractor."""
        return FeatureExtractor()

    @pytest.fixture
    def sample_trace(self):
        """Sample trace for testing."""
        return [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "CreditCheck", "timestamp": "2024-01-15T11:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
            {"activity": "GoodsIssued", "timestamp": "2024-01-17T10:00:00"},
            {"activity": "InvoiceCreated", "timestamp": "2024-01-18T10:00:00"},
        ]

    def test_extractor_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor.n_features > 0
        assert len(extractor.feature_names) > 0

    def test_extract_returns_extracted_features(self, extractor, sample_trace):
        """Test extract returns ExtractedFeatures."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert isinstance(result, ExtractedFeatures)
        assert result.case_id == "case_001"

    def test_extract_feature_vector(self, extractor, sample_trace):
        """Test feature vector is correct shape."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert isinstance(result.feature_vector, np.ndarray)
        assert len(result.feature_vector) == extractor.n_features

    def test_extract_feature_dict(self, extractor, sample_trace):
        """Test feature dictionary is populated."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert len(result.feature_dict) > 0
        for name in extractor.feature_names:
            assert name in result.feature_dict

    def test_extract_empty_trace(self, extractor):
        """Test extracting from empty trace."""
        result = extractor.extract([], case_id="case_001")

        assert result.case_id == "case_001"
        assert np.all(result.feature_vector == 0.0)
        assert result.metadata.get("empty") is True

    def test_temporal_features(self, extractor, sample_trace):
        """Test temporal features are extracted."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert "total_duration" in result.feature_dict
        assert "time_since_start" in result.feature_dict
        assert "avg_activity_duration" in result.feature_dict

        # Should have positive durations
        assert result.feature_dict["total_duration"] > 0

    def test_count_features(self, extractor, sample_trace):
        """Test count features are extracted."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert "event_count" in result.feature_dict
        assert "unique_activity_count" in result.feature_dict

        assert result.feature_dict["event_count"] == 5
        assert result.feature_dict["unique_activity_count"] == 5

    def test_pattern_features(self, extractor, sample_trace):
        """Test pattern features are extracted."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert "has_credit_block" in result.feature_dict
        assert "has_order_changes" in result.feature_dict
        assert "rework_count" in result.feature_dict

    def test_state_features(self, extractor, sample_trace):
        """Test state features are extracted."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert "current_stage" in result.feature_dict
        assert "completion_percentage" in result.feature_dict
        assert "is_blocked" in result.feature_dict

    def test_per_activity_counts(self, extractor, sample_trace):
        """Test per-activity count features."""
        result = extractor.extract(sample_trace, case_id="case_001")

        assert "count_OrderCreated" in result.feature_dict
        assert result.feature_dict["count_OrderCreated"] == 1

    def test_extract_with_credit_block(self, extractor):
        """Test extracting trace with credit block."""
        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "CreditBlock", "timestamp": "2024-01-15T11:00:00"},
            {"activity": "CreditRelease", "timestamp": "2024-01-15T14:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
        ]

        result = extractor.extract(trace, case_id="case_001")

        assert result.feature_dict["has_credit_block"] == 1.0
        assert result.feature_dict["credit_block_count"] == 1.0

    def test_extract_blocked_case(self, extractor):
        """Test extracting trace that is blocked."""
        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "CreditBlock", "timestamp": "2024-01-15T11:00:00"},
            # No CreditRelease
        ]

        result = extractor.extract(trace, case_id="case_001")

        assert result.feature_dict["is_blocked"] == 1.0

    def test_extract_with_order_changes(self, extractor):
        """Test extracting trace with order changes."""
        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "OrderChanged", "timestamp": "2024-01-15T11:00:00"},
            {"activity": "OrderChanged", "timestamp": "2024-01-15T12:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
        ]

        result = extractor.extract(trace, case_id="case_001")

        assert result.feature_dict["has_order_changes"] == 1.0
        assert result.feature_dict["order_change_count"] == 2.0

    def test_extract_batch(self, extractor):
        """Test batch feature extraction."""
        cases = [
            {
                "case_id": "case_001",
                "events": [
                    {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
                    {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
                ],
            },
            {
                "case_id": "case_002",
                "events": [
                    {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
                ],
            },
        ]

        matrix, case_ids, features = extractor.extract_batch(cases)

        assert matrix.shape[0] == 2
        assert matrix.shape[1] == extractor.n_features
        assert len(case_ids) == 2
        assert len(features) == 2

    def test_extracted_features_to_dict(self, extractor, sample_trace):
        """Test ExtractedFeatures to_dict method."""
        result = extractor.extract(sample_trace, case_id="case_001")
        data = result.to_dict()

        assert data["case_id"] == "case_001"
        assert "features" in data
        assert "extraction_timestamp" in data

    def test_extracted_features_get_feature(self, extractor, sample_trace):
        """Test getting specific feature value."""
        result = extractor.extract(sample_trace, case_id="case_001")

        event_count = result.get_feature("event_count")
        assert event_count == 5

        missing = result.get_feature("non_existent")
        assert missing is None


class TestConvenienceFeatureFunctions:
    """Tests for feature extraction convenience functions."""

    @pytest.fixture
    def sample_trace(self):
        """Sample trace for testing."""
        return [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
        ]

    def test_extract_features_function(self, sample_trace):
        """Test extract_features convenience function."""
        result = extract_features(sample_trace, case_id="case_001")

        assert isinstance(result, ExtractedFeatures)

    def test_extract_features_batch_function(self):
        """Test extract_features_batch convenience function."""
        cases = [
            {"case_id": "001", "events": [{"activity": "A", "timestamp": "2024-01-15T10:00:00"}]},
            {"case_id": "002", "events": [{"activity": "B", "timestamp": "2024-01-15T10:00:00"}]},
        ]

        matrix, case_ids = extract_features_batch(cases)

        assert matrix.shape[0] == 2
        assert len(case_ids) == 2


class TestModelConfig:
    """Tests for ModelConfig class."""

    def test_default_config(self):
        """Test default model configuration."""
        config = ModelConfig()

        assert config.model_type == ModelType.GRADIENT_BOOSTING
        assert config.n_estimators == 100
        assert config.max_depth == 10
        assert config.test_size == 0.2

    def test_custom_config(self):
        """Test custom model configuration."""
        config = ModelConfig(
            model_type=ModelType.RANDOM_FOREST,
            n_estimators=200,
            max_depth=15
        )

        assert config.model_type == ModelType.RANDOM_FOREST
        assert config.n_estimators == 200
        assert config.max_depth == 15


class TestClassificationModel:
    """Tests for ClassificationModel class."""

    @pytest.fixture
    def training_data(self):
        """Generate synthetic training data."""
        np.random.seed(42)
        n_samples = 200
        n_features = 29  # Match FeatureExtractor.n_features

        X = np.random.randn(n_samples, n_features)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)  # Simple decision boundary

        return X, y

    @pytest.fixture
    def model(self):
        """Create a classification model."""
        return ClassificationModel(PredictionType.LATE_DELIVERY)

    def test_model_initialization(self, model):
        """Test model initialization."""
        assert model.prediction_type == PredictionType.LATE_DELIVERY
        assert model.is_trained is False

    def test_model_train(self, model, training_data):
        """Test model training."""
        X, y = training_data

        result = model.train(X, y)

        assert model.is_trained is True
        assert isinstance(result, TrainingResult)

    def test_training_result_metrics(self, model, training_data):
        """Test training result contains metrics."""
        X, y = training_data

        result = model.train(X, y)

        assert "accuracy" in result.metrics
        assert "precision" in result.metrics
        assert "recall" in result.metrics
        assert "f1" in result.metrics
        assert "roc_auc" in result.metrics

    def test_training_result_feature_importances(self, model, training_data):
        """Test training result contains feature importances."""
        X, y = training_data
        feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        result = model.train(X, y, feature_names=feature_names)

        assert len(result.feature_importances) > 0

    def test_training_result_cv_scores(self, model, training_data):
        """Test training result contains CV scores."""
        X, y = training_data

        result = model.train(X, y)

        assert len(result.cv_scores) == 5  # Default 5-fold CV

    def test_model_predict(self, model, training_data):
        """Test model prediction."""
        X, y = training_data
        model.train(X, y)

        predictions = model.predict(X[:10])

        assert len(predictions) == 10
        assert all(isinstance(p, Prediction) for p in predictions)

    def test_model_predict_untrained_raises(self, model, training_data):
        """Test predicting with untrained model raises error."""
        X, y = training_data

        with pytest.raises(RuntimeError):
            model.predict(X[:10])

    def test_prediction_contents(self, model, training_data):
        """Test prediction object contents."""
        X, y = training_data
        model.train(X, y)

        predictions = model.predict(X[:1], case_ids=["case_001"])

        pred = predictions[0]
        assert pred.case_id == "case_001"
        assert pred.prediction_type == PredictionType.LATE_DELIVERY
        assert isinstance(pred.predicted_value, bool)
        assert 0 <= pred.probability <= 1
        assert pred.confidence in ["high", "medium", "low"]

    def test_predict_from_trace(self, model, training_data):
        """Test prediction from event trace."""
        X, y = training_data
        model.train(X, y)

        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
        ]

        prediction = model.predict_from_trace(trace, case_id="case_001")

        assert prediction.case_id == "case_001"
        assert len(prediction.features_used) > 0


class TestRegressionModel:
    """Tests for RegressionModel class."""

    @pytest.fixture
    def training_data(self):
        """Generate synthetic regression data."""
        np.random.seed(42)
        n_samples = 200
        n_features = 29  # Match FeatureExtractor.n_features

        X = np.random.randn(n_samples, n_features)
        y = X[:, 0] * 10 + X[:, 1] * 5 + np.random.randn(n_samples) * 2

        return X, y

    @pytest.fixture
    def model(self):
        """Create a regression model."""
        return RegressionModel(PredictionType.COMPLETION_TIME)

    def test_model_initialization(self, model):
        """Test model initialization."""
        assert model.prediction_type == PredictionType.COMPLETION_TIME
        assert model.is_trained is False

    def test_model_train(self, model, training_data):
        """Test model training."""
        X, y = training_data

        result = model.train(X, y)

        assert model.is_trained is True
        assert isinstance(result, TrainingResult)

    def test_training_result_metrics(self, model, training_data):
        """Test training result contains regression metrics."""
        X, y = training_data

        result = model.train(X, y)

        assert "mae" in result.metrics
        assert "mse" in result.metrics
        assert "rmse" in result.metrics
        assert "r2" in result.metrics

    def test_model_predict(self, model, training_data):
        """Test model prediction."""
        X, y = training_data
        model.train(X, y)

        predictions = model.predict(X[:10])

        assert len(predictions) == 10
        assert all(isinstance(p.predicted_value, float) for p in predictions)

    def test_prediction_no_probability(self, model, training_data):
        """Test regression predictions have no probability."""
        X, y = training_data
        model.train(X, y)

        predictions = model.predict(X[:1])

        assert predictions[0].probability is None


class TestModelFactoryFunctions:
    """Tests for model factory functions."""

    def test_create_late_delivery_model(self):
        """Test create_late_delivery_model function."""
        model = create_late_delivery_model()

        assert isinstance(model, ClassificationModel)
        assert model.prediction_type == PredictionType.LATE_DELIVERY

    def test_create_credit_hold_model(self):
        """Test create_credit_hold_model function."""
        model = create_credit_hold_model()

        assert isinstance(model, ClassificationModel)
        assert model.prediction_type == PredictionType.CREDIT_HOLD

    def test_create_completion_time_model(self):
        """Test create_completion_time_model function."""
        model = create_completion_time_model()

        assert isinstance(model, RegressionModel)
        assert model.prediction_type == PredictionType.COMPLETION_TIME


class TestPredictiveMonitor:
    """Tests for PredictiveMonitor class."""

    @pytest.fixture
    def training_data(self):
        """Generate synthetic training data."""
        np.random.seed(42)
        n_samples = 200
        n_features = 29  # Match FeatureExtractor.n_features

        X = np.random.randn(n_samples, n_features)
        y_class = (X[:, 0] + X[:, 1] > 0).astype(int)
        y_reg = X[:, 0] * 10 + X[:, 1] * 5

        return X, y_class, y_reg

    @pytest.fixture
    def monitor(self):
        """Create a predictive monitor."""
        return PredictiveMonitor()

    def test_monitor_initialization(self, monitor):
        """Test monitor initialization."""
        assert len(monitor._models) == 0

    def test_add_classifier(self, monitor):
        """Test adding classifier to monitor."""
        model = monitor.add_classifier(PredictionType.LATE_DELIVERY)

        assert isinstance(model, ClassificationModel)
        assert PredictionType.LATE_DELIVERY in monitor._models

    def test_add_regressor(self, monitor):
        """Test adding regressor to monitor."""
        model = monitor.add_regressor(PredictionType.COMPLETION_TIME)

        assert isinstance(model, RegressionModel)
        assert PredictionType.COMPLETION_TIME in monitor._models

    def test_get_model(self, monitor):
        """Test getting model from monitor."""
        monitor.add_classifier(PredictionType.LATE_DELIVERY)

        model = monitor.get_model(PredictionType.LATE_DELIVERY)

        assert model is not None
        assert model.prediction_type == PredictionType.LATE_DELIVERY

    def test_train_model(self, monitor, training_data):
        """Test training model through monitor."""
        X, y_class, _ = training_data

        monitor.add_classifier(PredictionType.LATE_DELIVERY)
        result = monitor.train_model(PredictionType.LATE_DELIVERY, X, y_class)

        assert isinstance(result, TrainingResult)

    def test_predict(self, monitor, training_data):
        """Test prediction through monitor."""
        X, y_class, _ = training_data

        monitor.add_classifier(PredictionType.LATE_DELIVERY)
        monitor.train_model(PredictionType.LATE_DELIVERY, X, y_class)

        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-16T10:00:00"},
        ]

        prediction = monitor.predict(
            PredictionType.LATE_DELIVERY,
            trace,
            case_id="case_001"
        )

        assert prediction.case_id == "case_001"

    def test_predict_all(self, monitor, training_data):
        """Test predicting with all models."""
        X, y_class, y_reg = training_data

        monitor.add_classifier(PredictionType.LATE_DELIVERY)
        monitor.add_regressor(PredictionType.COMPLETION_TIME)
        monitor.train_model(PredictionType.LATE_DELIVERY, X, y_class)
        monitor.train_model(PredictionType.COMPLETION_TIME, X, y_reg)

        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
        ]

        predictions = monitor.predict_all(trace, case_id="case_001")

        assert len(predictions) == 2

    def test_batch_predict(self, monitor, training_data):
        """Test batch prediction."""
        X, y_class, _ = training_data

        monitor.add_classifier(PredictionType.LATE_DELIVERY)
        monitor.train_model(PredictionType.LATE_DELIVERY, X, y_class)

        cases = [
            {"case_id": "001", "events": [{"activity": "A", "timestamp": "2024-01-15T10:00:00"}]},
            {"case_id": "002", "events": [{"activity": "B", "timestamp": "2024-01-15T10:00:00"}]},
        ]

        results = monitor.batch_predict(cases)

        assert len(results) == 2
        assert "001" in results
        assert "002" in results


class TestAlertSeverity:
    """Tests for AlertSeverity enumeration."""

    def test_severity_values(self):
        """Test severity values."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.LOW.value == "low"

    def test_severity_ordering(self):
        """Test severity comparison."""
        assert AlertSeverity.CRITICAL < AlertSeverity.HIGH
        assert AlertSeverity.HIGH < AlertSeverity.MEDIUM
        assert AlertSeverity.MEDIUM < AlertSeverity.LOW


class TestAlertType:
    """Tests for AlertType enumeration."""

    def test_alert_types_defined(self):
        """Test alert types are defined."""
        assert AlertType.LATE_DELIVERY_RISK.value == "late_delivery_risk"
        assert AlertType.CREDIT_HOLD_RISK.value == "credit_hold_risk"
        assert AlertType.SLA_WARNING.value == "sla_warning"


class TestAlertThreshold:
    """Tests for AlertThreshold class."""

    def test_threshold_creation(self):
        """Test threshold creation."""
        threshold = AlertThreshold(
            alert_type=AlertType.LATE_DELIVERY_RISK,
            prediction_type=PredictionType.LATE_DELIVERY,
            threshold_value=0.7,
            severity=AlertSeverity.HIGH
        )

        assert threshold.alert_type == AlertType.LATE_DELIVERY_RISK
        assert threshold.threshold_value == 0.7

    def test_threshold_check_gt(self):
        """Test threshold check with greater-than."""
        threshold = AlertThreshold(
            alert_type=AlertType.LATE_DELIVERY_RISK,
            prediction_type=PredictionType.LATE_DELIVERY,
            threshold_value=0.7,
            comparison="gt"
        )

        assert threshold.check(0.8) is True
        assert threshold.check(0.7) is False
        assert threshold.check(0.6) is False

    def test_threshold_check_gte(self):
        """Test threshold check with greater-than-or-equal."""
        threshold = AlertThreshold(
            alert_type=AlertType.LATE_DELIVERY_RISK,
            prediction_type=PredictionType.LATE_DELIVERY,
            threshold_value=0.7,
            comparison="gte"
        )

        assert threshold.check(0.8) is True
        assert threshold.check(0.7) is True
        assert threshold.check(0.6) is False

    def test_threshold_check_lt(self):
        """Test threshold check with less-than."""
        threshold = AlertThreshold(
            alert_type=AlertType.SLA_WARNING,
            prediction_type=PredictionType.COMPLETION_TIME,
            threshold_value=24.0,
            comparison="lt"
        )

        assert threshold.check(12.0) is True
        assert threshold.check(24.0) is False


class TestAlert:
    """Tests for Alert class."""

    @pytest.fixture
    def sample_prediction(self):
        """Create a sample prediction."""
        return Prediction(
            case_id="case_001",
            prediction_type=PredictionType.LATE_DELIVERY,
            predicted_value=True,
            probability=0.85
        )

    @pytest.fixture
    def sample_threshold(self):
        """Create a sample threshold."""
        return AlertThreshold(
            alert_type=AlertType.LATE_DELIVERY_RISK,
            prediction_type=PredictionType.LATE_DELIVERY,
            threshold_value=0.7,
            severity=AlertSeverity.HIGH
        )

    def test_alert_creation(self, sample_prediction, sample_threshold):
        """Test alert creation."""
        alert = Alert(
            alert_id="ALERT-000001",
            case_id="case_001",
            alert_type=AlertType.LATE_DELIVERY_RISK,
            severity=AlertSeverity.HIGH,
            prediction=sample_prediction,
            threshold=sample_threshold,
            message="High risk of late delivery"
        )

        assert alert.alert_id == "ALERT-000001"
        assert alert.case_id == "case_001"
        assert alert.acknowledged is False

    def test_alert_acknowledge(self, sample_prediction, sample_threshold):
        """Test acknowledging an alert."""
        alert = Alert(
            alert_id="ALERT-000001",
            case_id="case_001",
            alert_type=AlertType.LATE_DELIVERY_RISK,
            severity=AlertSeverity.HIGH,
            prediction=sample_prediction,
            threshold=sample_threshold,
            message="Test"
        )

        alert.acknowledge(user="admin")

        assert alert.acknowledged is True
        assert alert.acknowledged_by == "admin"
        assert alert.acknowledged_at is not None

    def test_alert_to_dict(self, sample_prediction, sample_threshold):
        """Test alert to_dict method."""
        alert = Alert(
            alert_id="ALERT-000001",
            case_id="case_001",
            alert_type=AlertType.LATE_DELIVERY_RISK,
            severity=AlertSeverity.HIGH,
            prediction=sample_prediction,
            threshold=sample_threshold,
            message="Test"
        )

        data = alert.to_dict()

        assert data["alert_id"] == "ALERT-000001"
        assert data["alert_type"] == "late_delivery_risk"
        assert data["severity"] == "high"


class TestAlertHandlers:
    """Tests for alert handler classes."""

    @pytest.fixture
    def sample_alert(self):
        """Create a sample alert."""
        prediction = Prediction(
            case_id="case_001",
            prediction_type=PredictionType.LATE_DELIVERY,
            predicted_value=True,
            probability=0.85
        )
        threshold = AlertThreshold(
            alert_type=AlertType.LATE_DELIVERY_RISK,
            prediction_type=PredictionType.LATE_DELIVERY,
            threshold_value=0.7
        )
        return Alert(
            alert_id="ALERT-000001",
            case_id="case_001",
            alert_type=AlertType.LATE_DELIVERY_RISK,
            severity=AlertSeverity.HIGH,
            prediction=prediction,
            threshold=threshold,
            message="Test alert"
        )

    def test_logging_handler(self, sample_alert):
        """Test LoggingAlertHandler."""
        handler = LoggingAlertHandler()

        # Should not raise
        handler.handle(sample_alert)

    def test_callback_handler(self, sample_alert):
        """Test CallbackAlertHandler."""
        received_alerts = []

        def callback(alert):
            received_alerts.append(alert)

        handler = CallbackAlertHandler(callback)
        handler.handle(sample_alert)

        assert len(received_alerts) == 1
        assert received_alerts[0] == sample_alert

    def test_queue_handler(self, sample_alert):
        """Test QueueAlertHandler."""
        handler = QueueAlertHandler()

        handler.handle(sample_alert)

        assert handler.size == 1

        alerts = handler.get_alerts()
        assert len(alerts) == 1
        assert alerts[0] == sample_alert

    def test_queue_handler_clear(self, sample_alert):
        """Test clearing queue handler."""
        handler = QueueAlertHandler()
        handler.handle(sample_alert)

        handler.clear()

        assert handler.size == 0

    def test_queue_handler_max_size(self):
        """Test queue handler respects max size."""
        handler = QueueAlertHandler(max_size=5)

        for i in range(10):
            prediction = Prediction(
                case_id=f"case_{i}",
                prediction_type=PredictionType.LATE_DELIVERY,
                predicted_value=True,
                probability=0.85
            )
            threshold = AlertThreshold(
                alert_type=AlertType.LATE_DELIVERY_RISK,
                prediction_type=PredictionType.LATE_DELIVERY,
                threshold_value=0.7
            )
            alert = Alert(
                alert_id=f"ALERT-{i:06d}",
                case_id=f"case_{i}",
                alert_type=AlertType.LATE_DELIVERY_RISK,
                severity=AlertSeverity.HIGH,
                prediction=prediction,
                threshold=threshold,
                message="Test"
            )
            handler.handle(alert)

        assert handler.size == 5


class TestAlertManager:
    """Tests for AlertManager class."""

    @pytest.fixture
    def manager(self):
        """Create an alert manager."""
        return AlertManager()

    @pytest.fixture
    def high_risk_prediction(self):
        """Create a high-risk prediction."""
        return Prediction(
            case_id="case_001",
            prediction_type=PredictionType.LATE_DELIVERY,
            predicted_value=True,
            probability=0.85
        )

    @pytest.fixture
    def low_risk_prediction(self):
        """Create a low-risk prediction."""
        return Prediction(
            case_id="case_002",
            prediction_type=PredictionType.LATE_DELIVERY,
            predicted_value=False,
            probability=0.3
        )

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert len(manager._thresholds) > 0  # Default thresholds

    def test_check_high_risk_prediction(self, manager, high_risk_prediction):
        """Test checking high-risk prediction generates alert."""
        alerts = manager.check_prediction(high_risk_prediction)

        assert len(alerts) > 0

    def test_check_low_risk_prediction(self, manager, low_risk_prediction):
        """Test checking low-risk prediction generates no alert."""
        alerts = manager.check_prediction(low_risk_prediction)

        assert len(alerts) == 0

    def test_add_handler(self, manager):
        """Test adding alert handler."""
        handler = QueueAlertHandler()
        manager.add_handler(handler)

        assert handler in manager._handlers

    def test_handler_receives_alerts(self, manager, high_risk_prediction):
        """Test handlers receive generated alerts."""
        handler = QueueAlertHandler()
        manager.add_handler(handler)

        manager.check_prediction(high_risk_prediction)

        assert handler.size > 0

    def test_add_custom_threshold(self, manager):
        """Test adding custom threshold."""
        threshold = AlertThreshold(
            alert_type=AlertType.SLA_WARNING,
            prediction_type=PredictionType.COMPLETION_TIME,
            threshold_value=100.0,
            comparison="gt"
        )

        manager.add_threshold(threshold)

        assert threshold in manager._thresholds

    def test_check_predictions_batch(self, manager, high_risk_prediction, low_risk_prediction):
        """Test checking multiple predictions."""
        alerts = manager.check_predictions([high_risk_prediction, low_risk_prediction])

        # Only high-risk should generate alert
        assert len(alerts) > 0
        assert all(a.case_id == "case_001" for a in alerts)

    def test_get_alerts_for_case(self, manager, high_risk_prediction):
        """Test getting alerts for specific case."""
        manager.check_prediction(high_risk_prediction)

        alerts = manager.get_alerts_for_case("case_001")

        assert len(alerts) > 0

    def test_get_active_alerts(self, manager, high_risk_prediction):
        """Test getting unacknowledged alerts."""
        manager.check_prediction(high_risk_prediction)

        active = manager.get_active_alerts()

        assert len(active) > 0
        assert all(not a.acknowledged for a in active)

    def test_acknowledge_alert(self, manager, high_risk_prediction):
        """Test acknowledging an alert."""
        alerts = manager.check_prediction(high_risk_prediction)
        alert_id = alerts[0].alert_id

        result = manager.acknowledge_alert(alert_id, user="admin")

        assert result is True

        active = manager.get_active_alerts()
        assert all(a.alert_id != alert_id for a in active)

    def test_get_alert_summary(self, manager, high_risk_prediction):
        """Test getting alert summary."""
        manager.check_prediction(high_risk_prediction)

        summary = manager.get_alert_summary()

        assert "total_alerts" in summary
        assert "active_alerts" in summary
        assert "by_severity" in summary
        assert "by_type" in summary

    def test_clear_history(self, manager, high_risk_prediction):
        """Test clearing alert history."""
        manager.check_prediction(high_risk_prediction)
        manager.clear_history()

        assert len(manager.get_active_alerts()) == 0

    def test_cooldown_prevents_duplicate_alerts(self, manager, high_risk_prediction):
        """Test cooldown prevents duplicate alerts."""
        alerts1 = manager.check_prediction(high_risk_prediction)
        alerts2 = manager.check_prediction(high_risk_prediction)

        # Second check should be in cooldown
        assert len(alerts2) < len(alerts1) or len(alerts2) == 0


class TestRiskScorer:
    """Tests for RiskScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a risk scorer."""
        return RiskScorer()

    def test_scorer_initialization(self, scorer):
        """Test scorer initialization."""
        assert len(scorer._weights) > 0

    def test_calculate_risk_score_empty(self, scorer):
        """Test risk score with no predictions."""
        score = scorer.calculate_risk_score([])

        assert score == 0.0

    def test_calculate_risk_score_single_prediction(self, scorer):
        """Test risk score with single prediction."""
        predictions = [
            Prediction(
                case_id="case_001",
                prediction_type=PredictionType.LATE_DELIVERY,
                predicted_value=True,
                probability=0.8
            )
        ]

        score = scorer.calculate_risk_score(predictions)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # High probability should mean high risk

    def test_calculate_risk_score_multiple_predictions(self, scorer):
        """Test risk score with multiple predictions."""
        predictions = [
            Prediction(
                case_id="case_001",
                prediction_type=PredictionType.LATE_DELIVERY,
                predicted_value=True,
                probability=0.9
            ),
            Prediction(
                case_id="case_001",
                prediction_type=PredictionType.CREDIT_HOLD,
                predicted_value=True,
                probability=0.7
            ),
        ]

        score = scorer.calculate_risk_score(predictions)

        assert 0.0 <= score <= 1.0

    def test_get_risk_level(self, scorer):
        """Test converting score to risk level."""
        assert scorer.get_risk_level(0.9) == "critical"
        assert scorer.get_risk_level(0.7) == "high"
        assert scorer.get_risk_level(0.5) == "medium"
        assert scorer.get_risk_level(0.3) == "low"
        assert scorer.get_risk_level(0.1) == "minimal"


class TestConvenienceAlertFunction:
    """Tests for create_alert_manager convenience function."""

    def test_create_alert_manager_defaults(self):
        """Test create_alert_manager with defaults."""
        manager = create_alert_manager()

        assert isinstance(manager, AlertManager)
        assert len(manager._handlers) > 0  # Should have logging handler

    def test_create_alert_manager_custom_thresholds(self):
        """Test create_alert_manager with custom thresholds."""
        manager = create_alert_manager(
            late_threshold=0.8,
            credit_threshold=0.7
        )

        # Find late delivery threshold
        late_thresholds = [
            t for t in manager._thresholds
            if t.prediction_type == PredictionType.LATE_DELIVERY
            and t.severity == AlertSeverity.HIGH
        ]

        assert len(late_thresholds) > 0
        assert late_thresholds[0].threshold_value == 0.8


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_feature_extraction_missing_activity_field(self):
        """Test feature extraction with missing activity field."""
        extractor = FeatureExtractor()
        trace = [
            {"type": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},  # 'type' instead of 'activity'
        ]

        result = extractor.extract(trace, case_id="case_001")

        # Should handle gracefully (type as fallback)
        assert result is not None

    def test_feature_extraction_missing_timestamp(self):
        """Test feature extraction with missing timestamps."""
        extractor = FeatureExtractor()
        trace = [
            {"activity": "OrderCreated"},  # No timestamp
            {"activity": "DeliveryCreated"},
        ]

        result = extractor.extract(trace, case_id="case_001")

        # Should handle gracefully
        assert result is not None
        assert result.feature_dict["event_count"] == 2

    def test_prediction_with_features_used(self):
        """Test that prediction includes features used."""
        np.random.seed(42)
        X = np.random.randn(100, 29)  # Match FeatureExtractor.n_features
        y = (X[:, 0] > 0).astype(int)

        model = ClassificationModel(PredictionType.LATE_DELIVERY)
        model.train(X, y)

        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-15T10:00:00"},
        ]

        prediction = model.predict_from_trace(trace)

        assert len(prediction.features_used) > 0

    def test_training_result_to_dict(self):
        """Test TrainingResult to_dict method."""
        result = TrainingResult(
            prediction_type=PredictionType.LATE_DELIVERY,
            model_type=ModelType.GRADIENT_BOOSTING,
            metrics={"accuracy": 0.9},
            feature_importances={"feature_0": 0.5},
            training_samples=100,
            cv_scores=[0.88, 0.90, 0.92]
        )

        data = result.to_dict()

        assert data["prediction_type"] == "late_delivery"
        assert data["model_type"] == "gradient_boosting"
        assert data["cv_mean"] == pytest.approx(0.9, abs=0.01)

    def test_alert_max_per_case(self):
        """Test max alerts per case limiting."""
        config = AlertConfig(max_alerts_per_case=2)
        manager = AlertManager(config)

        for i in range(5):
            prediction = Prediction(
                case_id="case_001",
                prediction_type=PredictionType.LATE_DELIVERY,
                predicted_value=True,
                probability=0.95
            )
            # Disable cooldown for this test
            manager._cooldown_tracker = {}
            manager.check_prediction(prediction)

        alerts = manager.get_alerts_for_case("case_001")

        # Should be limited to max_alerts_per_case
        assert len(alerts) <= config.max_alerts_per_case

    def test_prediction_to_dict(self):
        """Test Prediction to_dict method."""
        prediction = Prediction(
            case_id="case_001",
            prediction_type=PredictionType.LATE_DELIVERY,
            predicted_value=True,
            probability=0.85,
            confidence="high"
        )

        data = prediction.to_dict()

        assert data["case_id"] == "case_001"
        assert data["prediction_type"] == "late_delivery"
        assert data["predicted_value"] is True
        assert data["probability"] == 0.85
