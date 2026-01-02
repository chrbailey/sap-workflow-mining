"""
Machine Learning Models for Predictive Process Monitoring.

Provides ML model training and inference for predicting SAP O2C process
outcomes including delays, credit holds, and completion times. Uses
scikit-learn classifiers and regressors optimized for process data.

Supported Predictions:
- Late delivery prediction (binary classification)
- Credit hold prediction (binary classification)
- Completion time estimation (regression)

Model Types:
- RandomForestClassifier/Regressor: Good for interpretability
- GradientBoostingClassifier/Regressor: Often best performance
- Ensemble models: Combines multiple predictors

References:
- Teinemaa, I., et al. (2019). Outcome-oriented predictive process monitoring.
- Verenich, I., et al. (2019). Survey and cross-benchmark comparison of
  remaining time prediction methods in business process monitoring.
"""

import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        GradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
        VotingClassifier,
        VotingRegressor,
    )
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
        mean_absolute_error,
        mean_squared_error,
        r2_score,
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .features import FeatureExtractor, FeatureConfig, ExtractedFeatures

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of ML models available."""

    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    LOGISTIC_REGRESSION = "logistic_regression"
    RIDGE_REGRESSION = "ridge_regression"
    ENSEMBLE = "ensemble"


class PredictionType(Enum):
    """Types of predictions supported."""

    LATE_DELIVERY = "late_delivery"
    CREDIT_HOLD = "credit_hold"
    COMPLETION_TIME = "completion_time"


@dataclass
class ModelConfig:
    """
    Configuration for ML model training.

    Attributes:
        model_type: Type of model to train
        n_estimators: Number of trees for ensemble models
        max_depth: Maximum tree depth
        random_state: Random seed for reproducibility
        test_size: Fraction of data for testing
        cv_folds: Number of cross-validation folds
        scale_features: Whether to standardize features
    """
    model_type: ModelType = ModelType.GRADIENT_BOOSTING
    n_estimators: int = 100
    max_depth: int = 10
    random_state: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    scale_features: bool = True


@dataclass
class TrainingResult:
    """
    Results from model training.

    Attributes:
        prediction_type: Type of prediction this model makes
        model_type: Type of ML model trained
        metrics: Dictionary of evaluation metrics
        feature_importances: Feature importance scores
        training_samples: Number of training samples
        training_timestamp: When training was performed
        cv_scores: Cross-validation scores
    """
    prediction_type: PredictionType
    model_type: ModelType
    metrics: Dict[str, float]
    feature_importances: Dict[str, float]
    training_samples: int
    training_timestamp: datetime = field(default_factory=datetime.now)
    cv_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "prediction_type": self.prediction_type.value,
            "model_type": self.model_type.value,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
            "training_samples": self.training_samples,
            "training_timestamp": self.training_timestamp.isoformat(),
            "cv_scores": self.cv_scores,
            "cv_mean": np.mean(self.cv_scores) if self.cv_scores else 0.0,
            "cv_std": np.std(self.cv_scores) if self.cv_scores else 0.0,
        }


@dataclass
class Prediction:
    """
    A single prediction result.

    Attributes:
        case_id: Identifier for the process instance
        prediction_type: Type of prediction
        predicted_value: The predicted value (label or time)
        probability: Probability score for classification
        confidence: Confidence level of prediction
        timestamp: When prediction was made
        features_used: Features used for prediction
    """
    case_id: str
    prediction_type: PredictionType
    predicted_value: Union[bool, float, int]
    probability: Optional[float] = None
    confidence: str = "medium"
    timestamp: datetime = field(default_factory=datetime.now)
    features_used: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "case_id": self.case_id,
            "prediction_type": self.prediction_type.value,
            "predicted_value": self.predicted_value,
            "probability": self.probability,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


class PredictiveModel:
    """
    Base class for predictive process monitoring models.

    Wraps scikit-learn models with process mining-specific functionality
    including feature extraction, probability calibration, and confidence
    scoring.
    """

    def __init__(
        self,
        prediction_type: PredictionType,
        config: Optional[ModelConfig] = None,
        feature_config: Optional[FeatureConfig] = None
    ):
        """
        Initialize the predictive model.

        Args:
            prediction_type: Type of prediction (classification or regression)
            config: Model configuration
            feature_config: Feature extraction configuration
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for predictive models. "
                "Install with: pip install scikit-learn"
            )

        self._prediction_type = prediction_type
        self._config = config or ModelConfig()
        self._feature_config = feature_config or FeatureConfig()
        self._feature_extractor = FeatureExtractor(self._feature_config)

        self._model: Optional[Any] = None
        self._scaler: Optional[StandardScaler] = None
        self._is_trained = False
        self._feature_names: List[str] = []
        self._training_result: Optional[TrainingResult] = None

    @property
    def is_trained(self) -> bool:
        """Check if the model has been trained."""
        return self._is_trained

    @property
    def prediction_type(self) -> PredictionType:
        """Get the prediction type."""
        return self._prediction_type

    @property
    def feature_names(self) -> List[str]:
        """Get the feature names used by the model."""
        return self._feature_names.copy()

    @property
    def training_result(self) -> Optional[TrainingResult]:
        """Get the training result."""
        return self._training_result

    def _create_model(self) -> Any:
        """Create the underlying ML model based on configuration."""
        raise NotImplementedError("Subclasses must implement _create_model")

    def _get_feature_importances(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if self._model is None or not self._feature_names:
            return {}

        importances = {}
        if hasattr(self._model, "feature_importances_"):
            for name, importance in zip(
                self._feature_names, self._model.feature_importances_
            ):
                importances[name] = float(importance)
        elif hasattr(self._model, "coef_"):
            coef = self._model.coef_
            if coef.ndim > 1:
                coef = coef[0]
            for name, importance in zip(self._feature_names, np.abs(coef)):
                importances[name] = float(importance)

        # Sort by importance
        importances = dict(
            sorted(importances.items(), key=lambda x: x[1], reverse=True)
        )
        return importances


class ClassificationModel(PredictiveModel):
    """
    Classification model for binary outcome prediction.

    Predicts binary outcomes like "will be late" or "will require credit hold"
    with probability scores for risk assessment.

    Example:
        from prediction.models import ClassificationModel, PredictionType

        model = ClassificationModel(PredictionType.LATE_DELIVERY)

        # Train on historical data
        X_train = [...]  # Feature matrix
        y_train = [...]  # Labels (0 or 1)
        result = model.train(X_train, y_train)

        # Predict on new case
        prediction = model.predict_from_trace(trace, case_id="ORDER001")
        print(f"Late: {prediction.predicted_value}, P={prediction.probability}")
    """

    def _create_model(self) -> Any:
        """Create the classification model."""
        config = self._config

        if config.model_type == ModelType.RANDOM_FOREST:
            return RandomForestClassifier(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
                n_jobs=-1,
            )
        elif config.model_type == ModelType.GRADIENT_BOOSTING:
            return GradientBoostingClassifier(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )
        elif config.model_type == ModelType.LOGISTIC_REGRESSION:
            return LogisticRegression(
                random_state=config.random_state,
                max_iter=1000,
            )
        elif config.model_type == ModelType.ENSEMBLE:
            rf = RandomForestClassifier(
                n_estimators=config.n_estimators // 2,
                max_depth=config.max_depth,
                random_state=config.random_state,
                n_jobs=-1,
            )
            gb = GradientBoostingClassifier(
                n_estimators=config.n_estimators // 2,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )
            lr = LogisticRegression(
                random_state=config.random_state,
                max_iter=1000,
            )
            return VotingClassifier(
                estimators=[("rf", rf), ("gb", gb), ("lr", lr)],
                voting="soft",
            )
        else:
            return GradientBoostingClassifier(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> TrainingResult:
        """
        Train the classification model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,) - binary 0/1
            feature_names: Names of features

        Returns:
            TrainingResult with evaluation metrics
        """
        self._feature_names = feature_names or [
            f"feature_{i}" for i in range(X.shape[1])
        ]

        # Scale features if configured
        if self._config.scale_features:
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)
        else:
            X_scaled = X

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y,
            test_size=self._config.test_size,
            random_state=self._config.random_state,
            stratify=y,
        )

        # Create and train model
        self._model = self._create_model()
        self._model.fit(X_train, y_train)

        # Evaluate
        y_pred = self._model.predict(X_test)
        y_proba = self._model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_proba)),
        }

        # Cross-validation
        cv_scores = cross_val_score(
            self._model, X_scaled, y,
            cv=self._config.cv_folds,
            scoring="roc_auc",
        )

        self._is_trained = True
        self._training_result = TrainingResult(
            prediction_type=self._prediction_type,
            model_type=self._config.model_type,
            metrics=metrics,
            feature_importances=self._get_feature_importances(),
            training_samples=len(y),
            cv_scores=cv_scores.tolist(),
        )

        logger.info(
            f"Trained {self._prediction_type.value} classifier: "
            f"AUC={metrics['roc_auc']:.3f}, F1={metrics['f1']:.3f}"
        )

        return self._training_result

    def predict(
        self,
        X: np.ndarray,
        case_ids: Optional[List[str]] = None
    ) -> List[Prediction]:
        """
        Make predictions on feature matrix.

        Args:
            X: Feature matrix (n_samples, n_features)
            case_ids: Optional case identifiers

        Returns:
            List of Prediction objects
        """
        if not self._is_trained:
            raise RuntimeError("Model must be trained before prediction")

        if case_ids is None:
            case_ids = [f"case_{i}" for i in range(X.shape[0])]

        # Scale features
        if self._scaler is not None:
            X_scaled = self._scaler.transform(X)
        else:
            X_scaled = X

        # Predict
        y_pred = self._model.predict(X_scaled)
        y_proba = self._model.predict_proba(X_scaled)[:, 1]

        predictions = []
        for i, (case_id, pred, proba) in enumerate(zip(case_ids, y_pred, y_proba)):
            confidence = self._get_confidence_level(proba)
            predictions.append(Prediction(
                case_id=case_id,
                prediction_type=self._prediction_type,
                predicted_value=bool(pred),
                probability=float(proba),
                confidence=confidence,
            ))

        return predictions

    def predict_from_trace(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> Prediction:
        """
        Make prediction from an event trace.

        Args:
            trace: List of events with 'activity' and 'timestamp' fields
            case_id: Identifier for the process instance

        Returns:
            Prediction object
        """
        features = self._feature_extractor.extract(trace, case_id)
        predictions = self.predict(
            features.feature_vector.reshape(1, -1),
            case_ids=[case_id]
        )
        prediction = predictions[0]
        prediction.features_used = features.feature_dict
        return prediction

    def _get_confidence_level(self, probability: float) -> str:
        """Determine confidence level from probability."""
        if probability < 0.3 or probability > 0.7:
            return "high"
        elif probability < 0.4 or probability > 0.6:
            return "medium"
        else:
            return "low"


class RegressionModel(PredictiveModel):
    """
    Regression model for continuous outcome prediction.

    Predicts continuous values like estimated completion time or remaining
    duration for process instances.

    Example:
        from prediction.models import RegressionModel, PredictionType

        model = RegressionModel(PredictionType.COMPLETION_TIME)

        # Train on historical data
        X_train = [...]  # Feature matrix
        y_train = [...]  # Completion times in hours
        result = model.train(X_train, y_train)

        # Predict on new case
        prediction = model.predict_from_trace(trace, case_id="ORDER001")
        print(f"Estimated completion: {prediction.predicted_value} hours")
    """

    def _create_model(self) -> Any:
        """Create the regression model."""
        config = self._config

        if config.model_type == ModelType.RANDOM_FOREST:
            return RandomForestRegressor(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
                n_jobs=-1,
            )
        elif config.model_type == ModelType.GRADIENT_BOOSTING:
            return GradientBoostingRegressor(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )
        elif config.model_type == ModelType.RIDGE_REGRESSION:
            return Ridge(random_state=config.random_state)
        elif config.model_type == ModelType.ENSEMBLE:
            rf = RandomForestRegressor(
                n_estimators=config.n_estimators // 2,
                max_depth=config.max_depth,
                random_state=config.random_state,
                n_jobs=-1,
            )
            gb = GradientBoostingRegressor(
                n_estimators=config.n_estimators // 2,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )
            ridge = Ridge(random_state=config.random_state)
            return VotingRegressor(
                estimators=[("rf", rf), ("gb", gb), ("ridge", ridge)],
            )
        else:
            return GradientBoostingRegressor(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                random_state=config.random_state,
            )

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> TrainingResult:
        """
        Train the regression model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target values (n_samples,) - continuous values
            feature_names: Names of features

        Returns:
            TrainingResult with evaluation metrics
        """
        self._feature_names = feature_names or [
            f"feature_{i}" for i in range(X.shape[1])
        ]

        # Scale features if configured
        if self._config.scale_features:
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)
        else:
            X_scaled = X

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y,
            test_size=self._config.test_size,
            random_state=self._config.random_state,
        )

        # Create and train model
        self._model = self._create_model()
        self._model.fit(X_train, y_train)

        # Evaluate
        y_pred = self._model.predict(X_test)

        metrics = {
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "mse": float(mean_squared_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "r2": float(r2_score(y_test, y_pred)),
        }

        # Cross-validation
        cv_scores = cross_val_score(
            self._model, X_scaled, y,
            cv=self._config.cv_folds,
            scoring="r2",
        )

        self._is_trained = True
        self._training_result = TrainingResult(
            prediction_type=self._prediction_type,
            model_type=self._config.model_type,
            metrics=metrics,
            feature_importances=self._get_feature_importances(),
            training_samples=len(y),
            cv_scores=cv_scores.tolist(),
        )

        logger.info(
            f"Trained {self._prediction_type.value} regressor: "
            f"R2={metrics['r2']:.3f}, MAE={metrics['mae']:.2f}"
        )

        return self._training_result

    def predict(
        self,
        X: np.ndarray,
        case_ids: Optional[List[str]] = None
    ) -> List[Prediction]:
        """
        Make predictions on feature matrix.

        Args:
            X: Feature matrix (n_samples, n_features)
            case_ids: Optional case identifiers

        Returns:
            List of Prediction objects
        """
        if not self._is_trained:
            raise RuntimeError("Model must be trained before prediction")

        if case_ids is None:
            case_ids = [f"case_{i}" for i in range(X.shape[0])]

        # Scale features
        if self._scaler is not None:
            X_scaled = self._scaler.transform(X)
        else:
            X_scaled = X

        # Predict
        y_pred = self._model.predict(X_scaled)

        predictions = []
        for case_id, pred in zip(case_ids, y_pred):
            predictions.append(Prediction(
                case_id=case_id,
                prediction_type=self._prediction_type,
                predicted_value=float(pred),
                probability=None,
                confidence="medium",
            ))

        return predictions

    def predict_from_trace(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> Prediction:
        """
        Make prediction from an event trace.

        Args:
            trace: List of events with 'activity' and 'timestamp' fields
            case_id: Identifier for the process instance

        Returns:
            Prediction object
        """
        features = self._feature_extractor.extract(trace, case_id)
        predictions = self.predict(
            features.feature_vector.reshape(1, -1),
            case_ids=[case_id]
        )
        prediction = predictions[0]
        prediction.features_used = features.feature_dict
        return prediction


class PredictiveMonitor:
    """
    Orchestrates multiple predictive models for comprehensive process monitoring.

    Manages training and inference for multiple prediction types, providing
    a unified interface for predictive process monitoring.

    Example:
        from prediction.models import PredictiveMonitor

        monitor = PredictiveMonitor()

        # Train all models on historical data
        monitor.train_all(historical_cases, labels)

        # Get all predictions for a running case
        predictions = monitor.predict_all(trace, case_id="ORDER001")
        for pred in predictions:
            print(f"{pred.prediction_type.value}: {pred.predicted_value}")
    """

    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        feature_config: Optional[FeatureConfig] = None
    ):
        """
        Initialize the predictive monitor.

        Args:
            model_config: Configuration for ML models
            feature_config: Configuration for feature extraction
        """
        self._model_config = model_config or ModelConfig()
        self._feature_config = feature_config or FeatureConfig()
        self._feature_extractor = FeatureExtractor(self._feature_config)

        self._models: Dict[PredictionType, PredictiveModel] = {}

    def add_classifier(
        self,
        prediction_type: PredictionType,
        config: Optional[ModelConfig] = None
    ) -> ClassificationModel:
        """
        Add a classification model.

        Args:
            prediction_type: Type of prediction
            config: Model configuration

        Returns:
            The created ClassificationModel
        """
        model = ClassificationModel(
            prediction_type,
            config or self._model_config,
            self._feature_config,
        )
        self._models[prediction_type] = model
        return model

    def add_regressor(
        self,
        prediction_type: PredictionType,
        config: Optional[ModelConfig] = None
    ) -> RegressionModel:
        """
        Add a regression model.

        Args:
            prediction_type: Type of prediction
            config: Model configuration

        Returns:
            The created RegressionModel
        """
        model = RegressionModel(
            prediction_type,
            config or self._model_config,
            self._feature_config,
        )
        self._models[prediction_type] = model
        return model

    def get_model(self, prediction_type: PredictionType) -> Optional[PredictiveModel]:
        """Get a model by prediction type."""
        return self._models.get(prediction_type)

    def train_model(
        self,
        prediction_type: PredictionType,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> TrainingResult:
        """
        Train a specific model.

        Args:
            prediction_type: Type of prediction
            X: Feature matrix
            y: Target values
            feature_names: Feature names

        Returns:
            TrainingResult
        """
        model = self._models.get(prediction_type)
        if model is None:
            raise ValueError(f"No model registered for {prediction_type.value}")

        return model.train(X, y, feature_names)

    def predict(
        self,
        prediction_type: PredictionType,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> Prediction:
        """
        Make a prediction of a specific type.

        Args:
            prediction_type: Type of prediction
            trace: Event trace
            case_id: Case identifier

        Returns:
            Prediction object
        """
        model = self._models.get(prediction_type)
        if model is None:
            raise ValueError(f"No model registered for {prediction_type.value}")

        if not model.is_trained:
            raise RuntimeError(
                f"Model for {prediction_type.value} must be trained first"
            )

        return model.predict_from_trace(trace, case_id)

    def predict_all(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> List[Prediction]:
        """
        Make all available predictions for a trace.

        Args:
            trace: Event trace
            case_id: Case identifier

        Returns:
            List of predictions from all trained models
        """
        predictions = []
        for prediction_type, model in self._models.items():
            if model.is_trained:
                try:
                    pred = model.predict_from_trace(trace, case_id)
                    predictions.append(pred)
                except Exception as e:
                    logger.warning(
                        f"Prediction failed for {prediction_type.value}: {e}"
                    )

        return predictions

    def batch_predict(
        self,
        cases: List[Dict[str, Any]],
        case_id_field: str = "case_id",
        events_field: str = "events"
    ) -> Dict[str, List[Prediction]]:
        """
        Make predictions for multiple cases.

        Args:
            cases: List of cases with events
            case_id_field: Field name for case ID
            events_field: Field name for events list

        Returns:
            Dictionary mapping case_id to list of predictions
        """
        results: Dict[str, List[Prediction]] = {}

        for case in cases:
            case_id = str(case.get(case_id_field, "unknown"))
            events = case.get(events_field, [])

            predictions = self.predict_all(events, case_id)
            results[case_id] = predictions

        return results

    def save(self, path: Union[str, Path]) -> None:
        """
        Save all trained models to disk.

        Args:
            path: Directory path to save models
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        for prediction_type, model in self._models.items():
            if model.is_trained:
                model_path = path / f"{prediction_type.value}.pkl"
                with open(model_path, "wb") as f:
                    pickle.dump({
                        "model": model._model,
                        "scaler": model._scaler,
                        "feature_names": model._feature_names,
                        "config": model._config,
                        "training_result": model._training_result,
                    }, f)

        logger.info(f"Saved models to {path}")

    def load(self, path: Union[str, Path]) -> None:
        """
        Load trained models from disk.

        Args:
            path: Directory path containing saved models
        """
        path = Path(path)

        for model_file in path.glob("*.pkl"):
            prediction_type_str = model_file.stem
            try:
                prediction_type = PredictionType(prediction_type_str)
            except ValueError:
                logger.warning(f"Unknown prediction type: {prediction_type_str}")
                continue

            with open(model_file, "rb") as f:
                data = pickle.load(f)

            # Determine model class from prediction type
            if prediction_type == PredictionType.COMPLETION_TIME:
                model = RegressionModel(prediction_type, data["config"])
            else:
                model = ClassificationModel(prediction_type, data["config"])

            model._model = data["model"]
            model._scaler = data["scaler"]
            model._feature_names = data["feature_names"]
            model._training_result = data["training_result"]
            model._is_trained = True

            self._models[prediction_type] = model

        logger.info(f"Loaded models from {path}")


def create_late_delivery_model(
    config: Optional[ModelConfig] = None
) -> ClassificationModel:
    """
    Create a model for predicting late deliveries.

    Args:
        config: Model configuration

    Returns:
        ClassificationModel for late delivery prediction
    """
    return ClassificationModel(PredictionType.LATE_DELIVERY, config)


def create_credit_hold_model(
    config: Optional[ModelConfig] = None
) -> ClassificationModel:
    """
    Create a model for predicting credit holds.

    Args:
        config: Model configuration

    Returns:
        ClassificationModel for credit hold prediction
    """
    return ClassificationModel(PredictionType.CREDIT_HOLD, config)


def create_completion_time_model(
    config: Optional[ModelConfig] = None
) -> RegressionModel:
    """
    Create a model for predicting completion times.

    Args:
        config: Model configuration

    Returns:
        RegressionModel for completion time prediction
    """
    return RegressionModel(PredictionType.COMPLETION_TIME, config)
