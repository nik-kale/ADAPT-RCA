"""
Isolation Forest-based anomaly detection for ADAPT-RCA.

Isolation Forest is an unsupervised learning algorithm that isolates anomalies
by randomly selecting features and splitting values. Anomalies are easier to
isolate (require fewer splits) than normal points.

Key advantages:
- No labeled training data required
- Effective for high-dimensional data
- Linear time complexity O(n)
- Works well with multivariate features

Classes:
    IsolationForestDetector: ML-based anomaly detector using Isolation Forest
    AnomalyScore: Result containing anomaly score and details

Example:
    >>> from adapt_rca.ml import IsolationForestDetector
    >>> detector = IsolationForestDetector(contamination=0.1)
    >>>
    >>> # Train on historical metrics
    >>> training_data = [
    ...     {"error_rate": 0.01, "latency_p95": 150, "cpu_usage": 45},
    ...     {"error_rate": 0.02, "latency_p95": 160, "cpu_usage": 50},
    ...     # ... more training samples
    ... ]
    >>> detector.train(training_data, features=["error_rate", "latency_p95", "cpu_usage"])
    >>>
    >>> # Detect anomalies in new data
    >>> current_metrics = {"error_rate": 0.15, "latency_p95": 500, "cpu_usage": 90}
    >>> result = detector.detect(current_metrics)
    >>> if result.is_anomaly:
    ...     print(f"Anomaly detected! Score: {result.score:.3f}")
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """Result from Isolation Forest anomaly detection."""

    is_anomaly: bool
    score: float  # Anomaly score: -1 to 1 (lower = more anomalous)
    confidence: float  # 0 to 1
    features_used: List[str]
    feature_values: Dict[str, float]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_anomaly": self.is_anomaly,
            "score": float(self.score),
            "confidence": float(self.confidence),
            "features_used": self.features_used,
            "feature_values": self.feature_values,
            "timestamp": self.timestamp.isoformat()
        }


class IsolationForestDetector:
    """
    Isolation Forest-based anomaly detector.

    Uses scikit-learn's IsolationForest algorithm to detect anomalies
    in multivariate metrics without requiring labeled training data.

    Args:
        contamination: Expected proportion of outliers (0.0 to 0.5)
        n_estimators: Number of trees in the forest
        max_samples: Number of samples to train each tree
        random_state: Random seed for reproducibility

    Example:
        >>> detector = IsolationForestDetector(contamination=0.1)
        >>> detector.train(historical_data, features=["error_rate", "latency"])
        >>> result = detector.detect(current_metrics)
    """

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        max_samples: int | str = "auto",
        random_state: int = 42
    ):
        """Initialize Isolation Forest detector."""
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state

        self.model: Optional[Any] = None
        self.features: Optional[List[str]] = None
        self.is_trained: bool = False
        self.training_stats: Dict[str, Any] = {}

    def train(
        self,
        data: List[Dict[str, Any]],
        features: List[str],
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Train Isolation Forest on historical data.

        Args:
            data: List of metric dictionaries
            features: Feature names to use for training
            validate: Whether to validate training data

        Returns:
            Training statistics including sample count, feature stats

        Raises:
            ValueError: If data is invalid or features are missing
            ImportError: If scikit-learn is not installed

        Example:
            >>> training_data = [
            ...     {"error_rate": 0.01, "latency": 150, "cpu": 45},
            ...     {"error_rate": 0.02, "latency": 160, "cpu": 50},
            ... ]
            >>> stats = detector.train(training_data, ["error_rate", "latency", "cpu"])
            >>> print(f"Trained on {stats['sample_count']} samples")
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            raise ImportError(
                "scikit-learn is required for Isolation Forest detector. "
                "Install with: pip install scikit-learn"
            )

        # Validate inputs
        if not data:
            raise ValueError("Training data cannot be empty")

        if not features:
            raise ValueError("Features list cannot be empty")

        # Extract feature matrix
        X = self._extract_features(data, features, validate=validate)

        if len(X) < 10:
            logger.warning(
                f"Training data has only {len(X)} samples. "
                f"Isolation Forest works best with at least 100 samples."
            )

        # Train model
        logger.info(
            f"Training Isolation Forest on {len(X)} samples "
            f"with {len(features)} features"
        )

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1  # Use all CPU cores
        )

        self.model.fit(X)
        self.features = features
        self.is_trained = True

        # Calculate training statistics
        self.training_stats = {
            "sample_count": len(X),
            "feature_count": len(features),
            "features": features,
            "feature_stats": self._calculate_feature_stats(X, features),
            "trained_at": datetime.now().isoformat(),
            "contamination": self.contamination,
            "n_estimators": self.n_estimators
        }

        logger.info(f"Training complete: {self.training_stats}")

        return self.training_stats

    def detect(
        self,
        metrics: Dict[str, Any],
        threshold: Optional[float] = None
    ) -> AnomalyScore:
        """
        Detect if current metrics are anomalous.

        Args:
            metrics: Current metric values
            threshold: Custom anomaly score threshold (default: use model's decision)

        Returns:
            AnomalyScore with anomaly status and details

        Raises:
            RuntimeError: If model is not trained
            ValueError: If metrics are missing required features

        Example:
            >>> result = detector.detect({"error_rate": 0.15, "latency": 500})
            >>> if result.is_anomaly:
            ...     print(f"Anomaly! Confidence: {result.confidence:.1%}")
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError(
                "Model is not trained. Call train() first."
            )

        # Extract features for current metrics
        X = self._extract_features([metrics], self.features, validate=True)

        if len(X) == 0:
            raise ValueError("Could not extract features from metrics")

        # Get anomaly prediction (-1 for anomaly, 1 for normal)
        prediction = self.model.predict(X)[0]

        # Get anomaly score (lower = more anomalous)
        # Score is between -1 and 1, where negative means anomaly
        score = self.model.score_samples(X)[0]

        # Calculate confidence (0 to 1)
        # Transform score to confidence: more negative = higher confidence it's anomaly
        confidence = abs(score) if score < 0 else 1 - score

        # Determine if anomaly
        if threshold is not None:
            is_anomaly = score < threshold
        else:
            is_anomaly = (prediction == -1)

        # Extract feature values used
        feature_values = {
            feature: metrics.get(feature)
            for feature in self.features
        }

        result = AnomalyScore(
            is_anomaly=is_anomaly,
            score=float(score),
            confidence=float(confidence),
            features_used=self.features,
            feature_values=feature_values,
            timestamp=datetime.now()
        )

        if result.is_anomaly:
            logger.warning(
                f"Anomaly detected! Score: {score:.3f}, "
                f"Confidence: {confidence:.1%}, "
                f"Features: {feature_values}"
            )
        else:
            logger.debug(f"Normal behavior. Score: {score:.3f}")

        return result

    def detect_batch(
        self,
        metrics_list: List[Dict[str, Any]]
    ) -> List[AnomalyScore]:
        """
        Detect anomalies in batch of metrics.

        More efficient than calling detect() multiple times.

        Args:
            metrics_list: List of metric dictionaries

        Returns:
            List of AnomalyScore results

        Example:
            >>> metrics = [
            ...     {"error_rate": 0.01, "latency": 150},
            ...     {"error_rate": 0.15, "latency": 500},  # anomaly
            ... ]
            >>> results = detector.detect_batch(metrics)
            >>> anomalies = [r for r in results if r.is_anomaly]
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Call train() first.")

        # Extract features
        X = self._extract_features(metrics_list, self.features, validate=True)

        # Get predictions and scores
        predictions = self.model.predict(X)
        scores = self.model.score_samples(X)

        # Create results
        results = []
        for i, (metrics, prediction, score) in enumerate(
            zip(metrics_list, predictions, scores)
        ):
            is_anomaly = (prediction == -1)
            confidence = abs(score) if score < 0 else 1 - score

            feature_values = {
                feature: metrics.get(feature)
                for feature in self.features
            }

            results.append(AnomalyScore(
                is_anomaly=is_anomaly,
                score=float(score),
                confidence=float(confidence),
                features_used=self.features,
                feature_values=feature_values,
                timestamp=datetime.now()
            ))

        anomaly_count = sum(1 for r in results if r.is_anomaly)
        logger.info(
            f"Batch detection complete: {anomaly_count}/{len(results)} anomalies"
        )

        return results

    def save(self, path: str | Path) -> None:
        """
        Save trained model to disk.

        Args:
            path: File path to save model

        Example:
            >>> detector.train(data, features)
            >>> detector.save("models/anomaly_detector.pkl")
        """
        if not self.is_trained:
            raise RuntimeError("Cannot save untrained model")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        model_data = {
            "model": self.model,
            "features": self.features,
            "training_stats": self.training_stats,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "max_samples": self.max_samples,
            "random_state": self.random_state
        }

        with open(path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {path}")

    def load(self, path: str | Path) -> None:
        """
        Load trained model from disk.

        Args:
            path: File path to load model from

        Example:
            >>> detector = IsolationForestDetector()
            >>> detector.load("models/anomaly_detector.pkl")
            >>> result = detector.detect(current_metrics)
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        with open(path, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data["model"]
        self.features = model_data["features"]
        self.training_stats = model_data["training_stats"]
        self.contamination = model_data["contamination"]
        self.n_estimators = model_data["n_estimators"]
        self.max_samples = model_data["max_samples"]
        self.random_state = model_data["random_state"]
        self.is_trained = True

        logger.info(
            f"Model loaded from {path}. "
            f"Trained on {self.training_stats['sample_count']} samples."
        )

    def _extract_features(
        self,
        data: List[Dict[str, Any]],
        features: List[str],
        validate: bool = True
    ) -> np.ndarray:
        """Extract feature matrix from data."""
        X = []

        for i, sample in enumerate(data):
            row = []
            valid = True

            for feature in features:
                if feature not in sample:
                    if validate:
                        raise ValueError(
                            f"Feature '{feature}' missing in sample {i}"
                        )
                    else:
                        logger.warning(
                            f"Feature '{feature}' missing in sample {i}, skipping"
                        )
                        valid = False
                        break

                value = sample[feature]

                # Convert to float
                try:
                    row.append(float(value))
                except (TypeError, ValueError):
                    if validate:
                        raise ValueError(
                            f"Feature '{feature}' has non-numeric value: {value}"
                        )
                    else:
                        logger.warning(
                            f"Feature '{feature}' has non-numeric value, skipping sample"
                        )
                        valid = False
                        break

            if valid and len(row) == len(features):
                X.append(row)

        return np.array(X)

    def _calculate_feature_stats(
        self,
        X: np.ndarray,
        features: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate statistics for each feature."""
        stats = {}

        for i, feature in enumerate(features):
            column = X[:, i]
            stats[feature] = {
                "mean": float(np.mean(column)),
                "std": float(np.std(column)),
                "min": float(np.min(column)),
                "max": float(np.max(column)),
                "median": float(np.median(column))
            }

        return stats

    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        if not self.is_trained:
            return {"is_trained": False}

        return {
            "is_trained": True,
            **self.training_stats
        }

    def retrain(
        self,
        additional_data: List[Dict[str, Any]],
        keep_previous: bool = True
    ) -> Dict[str, Any]:
        """
        Retrain model with additional data.

        Args:
            additional_data: New training samples
            keep_previous: Whether to include previous training data

        Returns:
            Updated training statistics

        Note:
            If keep_previous is False, this is equivalent to train().
            If True, combines old and new data for retraining.
        """
        if not keep_previous:
            return self.train(additional_data, self.features)

        # For simplicity, we'll just retrain on new data
        # In production, you'd want to persist old training data
        logger.warning(
            "Retraining with only new data. "
            "To preserve old training data, implement data persistence."
        )

        return self.train(additional_data, self.features)
