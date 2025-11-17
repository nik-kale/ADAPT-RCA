"""
ML Model Manager for ADAPT-RCA.

Manages lifecycle of ML models including:
- Model registration and versioning
- Persistence and loading
- Performance monitoring
- Automatic retraining triggers

Classes:
    MLModelManager: Central manager for ML models
    ModelMetadata: Model information and statistics

Example:
    >>> from adapt_rca.ml import MLModelManager, IsolationForestDetector
    >>> manager = MLModelManager(models_dir="models/")
    >>>
    >>> # Register and save model
    >>> detector = IsolationForestDetector()
    >>> detector.train(data, features)
    >>> manager.register_model("service-anomaly-v1", detector, metadata={
    ...     "service": "api-gateway",
    ...     "features": ["error_rate", "latency"]
    ... })
    >>>
    >>> # Load and use model
    >>> detector = manager.load_model("service-anomaly-v1")
    >>> result = detector.detect(current_metrics)
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for ML model."""

    name: str
    model_type: str  # "isolation_forest" or "lstm"
    version: str
    created_at: datetime
    updated_at: datetime
    training_samples: int
    performance_metrics: Dict[str, float]
    custom_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "model_type": self.model_type,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "training_samples": self.training_samples,
            "performance_metrics": self.performance_metrics,
            "custom_metadata": self.custom_metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            model_type=data["model_type"],
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            training_samples=data["training_samples"],
            performance_metrics=data["performance_metrics"],
            custom_metadata=data["custom_metadata"]
        )


class MLModelManager:
    """
    Central manager for ML models.

    Handles model lifecycle including registration, persistence,
    versioning, and performance monitoring.

    Args:
        models_dir: Directory to store models
        auto_cleanup: Whether to auto-cleanup old model versions
        max_versions: Maximum versions to keep per model

    Example:
        >>> manager = MLModelManager(models_dir="models/")
        >>> manager.register_model("my-model", detector)
        >>> detector = manager.load_model("my-model")
    """

    def __init__(
        self,
        models_dir: str | Path = "models",
        auto_cleanup: bool = True,
        max_versions: int = 5
    ):
        """Initialize model manager."""
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.auto_cleanup = auto_cleanup
        self.max_versions = max_versions

        self.registry_file = self.models_dir / "registry.json"
        self.registry: Dict[str, List[ModelMetadata]] = self._load_registry()

        logger.info(f"Initialized MLModelManager at {self.models_dir}")

    def register_model(
        self,
        name: str,
        model: Any,
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None
    ) -> ModelMetadata:
        """
        Register and save a trained model.

        Args:
            name: Model name (unique identifier)
            model: Trained model instance (IsolationForestDetector or LSTMTimeSeriesDetector)
            metadata: Additional metadata
            version: Version string (defaults to timestamp)

        Returns:
            ModelMetadata for registered model

        Example:
            >>> detector = IsolationForestDetector()
            >>> detector.train(data, features)
            >>> metadata = manager.register_model(
            ...     "api-anomaly",
            ...     detector,
            ...     metadata={"service": "api-gateway"}
            ... )
        """
        from .isolation_forest import IsolationForestDetector
        from .lstm_detector import LSTMTimeSeriesDetector

        # Determine model type
        if isinstance(model, IsolationForestDetector):
            model_type = "isolation_forest"
        elif isinstance(model, LSTMTimeSeriesDetector):
            model_type = "lstm"
        else:
            raise ValueError(f"Unsupported model type: {type(model)}")

        # Generate version if not provided
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create model directory
        model_dir = self.models_dir / name / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        model.save(model_dir)

        # Get training stats
        training_stats = model.get_training_stats()

        # Create metadata
        now = datetime.now()
        model_metadata = ModelMetadata(
            name=name,
            model_type=model_type,
            version=version,
            created_at=now,
            updated_at=now,
            training_samples=training_stats.get("sample_count", 0),
            performance_metrics={},
            custom_metadata=metadata or {}
        )

        # Add to registry
        if name not in self.registry:
            self.registry[name] = []

        self.registry[name].append(model_metadata)

        # Save registry
        self._save_registry()

        # Auto-cleanup old versions
        if self.auto_cleanup:
            self._cleanup_old_versions(name)

        logger.info(f"Registered model '{name}' version '{version}' ({model_type})")

        return model_metadata

    def load_model(
        self,
        name: str,
        version: Optional[str] = None
    ) -> Any:
        """
        Load a registered model.

        Args:
            name: Model name
            version: Specific version (defaults to latest)

        Returns:
            Loaded model instance

        Raises:
            ValueError: If model not found

        Example:
            >>> detector = manager.load_model("api-anomaly")
            >>> result = detector.detect(metrics)
        """
        from .isolation_forest import IsolationForestDetector
        from .lstm_detector import LSTMTimeSeriesDetector

        if name not in self.registry:
            raise ValueError(f"Model '{name}' not found in registry")

        # Get model metadata
        versions = self.registry[name]

        if version is None:
            # Get latest version
            metadata = max(versions, key=lambda m: m.updated_at)
        else:
            # Get specific version
            metadata = next(
                (m for m in versions if m.version == version),
                None
            )
            if metadata is None:
                raise ValueError(
                    f"Version '{version}' not found for model '{name}'"
                )

        # Load model
        model_dir = self.models_dir / name / metadata.version

        if metadata.model_type == "isolation_forest":
            # For Isolation Forest, load from pickle file
            model = IsolationForestDetector()
            model_file = model_dir / "model.pkl"
            if not model_file.exists():
                # Try alternative naming
                model_file = model_dir
            model.load(model_file)

        elif metadata.model_type == "lstm":
            # For LSTM, load from directory with model.h5
            model = LSTMTimeSeriesDetector()
            model.load(model_dir)

        else:
            raise ValueError(f"Unknown model type: {metadata.model_type}")

        logger.info(
            f"Loaded model '{name}' version '{metadata.version}' ({metadata.model_type})"
        )

        return model

    def list_models(self) -> List[str]:
        """List all registered model names."""
        return list(self.registry.keys())

    def get_model_info(self, name: str) -> List[ModelMetadata]:
        """
        Get information about all versions of a model.

        Args:
            name: Model name

        Returns:
            List of ModelMetadata for all versions

        Example:
            >>> versions = manager.get_model_info("api-anomaly")
            >>> for v in versions:
            ...     print(f"Version {v.version}: {v.training_samples} samples")
        """
        if name not in self.registry:
            raise ValueError(f"Model '{name}' not found")

        return self.registry[name]

    def delete_model(
        self,
        name: str,
        version: Optional[str] = None
    ) -> None:
        """
        Delete a model or specific version.

        Args:
            name: Model name
            version: Specific version (deletes all versions if None)

        Example:
            >>> # Delete specific version
            >>> manager.delete_model("api-anomaly", version="20240101_120000")
            >>>
            >>> # Delete all versions
            >>> manager.delete_model("api-anomaly")
        """
        if name not in self.registry:
            raise ValueError(f"Model '{name}' not found")

        if version is None:
            # Delete all versions
            model_dir = self.models_dir / name
            if model_dir.exists():
                import shutil
                shutil.rmtree(model_dir)

            del self.registry[name]
            logger.info(f"Deleted all versions of model '{name}'")

        else:
            # Delete specific version
            version_dir = self.models_dir / name / version
            if version_dir.exists():
                import shutil
                shutil.rmtree(version_dir)

            # Remove from registry
            self.registry[name] = [
                m for m in self.registry[name]
                if m.version != version
            ]

            # If no versions left, remove model entry
            if not self.registry[name]:
                del self.registry[name]

            logger.info(f"Deleted model '{name}' version '{version}'")

        self._save_registry()

    def update_performance_metrics(
        self,
        name: str,
        metrics: Dict[str, float],
        version: Optional[str] = None
    ) -> None:
        """
        Update performance metrics for a model.

        Args:
            name: Model name
            metrics: Performance metrics (e.g., precision, recall, f1)
            version: Specific version (defaults to latest)

        Example:
            >>> manager.update_performance_metrics(
            ...     "api-anomaly",
            ...     {"precision": 0.92, "recall": 0.88, "f1": 0.90}
            ... )
        """
        if name not in self.registry:
            raise ValueError(f"Model '{name}' not found")

        versions = self.registry[name]

        if version is None:
            # Update latest version
            metadata = max(versions, key=lambda m: m.updated_at)
        else:
            metadata = next(
                (m for m in versions if m.version == version),
                None
            )
            if metadata is None:
                raise ValueError(f"Version '{version}' not found")

        # Update metrics
        metadata.performance_metrics.update(metrics)
        metadata.updated_at = datetime.now()

        self._save_registry()

        logger.info(f"Updated metrics for '{name}' v{metadata.version}: {metrics}")

    def _load_registry(self) -> Dict[str, List[ModelMetadata]]:
        """Load registry from disk."""
        if not self.registry_file.exists():
            return {}

        with open(self.registry_file, 'r') as f:
            data = json.load(f)

        registry = {}
        for name, versions_data in data.items():
            registry[name] = [
                ModelMetadata.from_dict(v)
                for v in versions_data
            ]

        return registry

    def _save_registry(self) -> None:
        """Save registry to disk."""
        data = {
            name: [m.to_dict() for m in versions]
            for name, versions in self.registry.items()
        }

        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _cleanup_old_versions(self, name: str) -> None:
        """Clean up old model versions."""
        if name not in self.registry:
            return

        versions = self.registry[name]

        if len(versions) <= self.max_versions:
            return

        # Sort by updated_at (newest first)
        versions.sort(key=lambda m: m.updated_at, reverse=True)

        # Keep only max_versions
        to_keep = versions[:self.max_versions]
        to_delete = versions[self.max_versions:]

        for metadata in to_delete:
            version_dir = self.models_dir / name / metadata.version
            if version_dir.exists():
                import shutil
                shutil.rmtree(version_dir)
                logger.info(
                    f"Cleaned up old version: '{name}' v{metadata.version}"
                )

        # Update registry
        self.registry[name] = to_keep
        self._save_registry()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all models.

        Returns:
            Summary statistics

        Example:
            >>> summary = manager.get_summary()
            >>> print(f"Total models: {summary['total_models']}")
        """
        total_models = len(self.registry)
        total_versions = sum(len(versions) for versions in self.registry.values())

        models_by_type = {}
        for versions in self.registry.values():
            for metadata in versions:
                model_type = metadata.model_type
                models_by_type[model_type] = models_by_type.get(model_type, 0) + 1

        return {
            "total_models": total_models,
            "total_versions": total_versions,
            "models_by_type": models_by_type,
            "models_dir": str(self.models_dir),
            "max_versions": self.max_versions
        }
