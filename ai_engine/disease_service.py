"""
Disease Detection Service
=========================

Loads pre-trained TensorFlow CNN models for crop disease classification.
Supports: Corn, Potato, Rice, Wheat
Models are loaded once at first use and cached in memory.
"""

import os
import ast
import logging
from pathlib import Path
import numpy as np
from PIL import Image
from io import BytesIO
from django.conf import settings
from .models import AIModelArtifact

logger = logging.getLogger(__name__)

# ============================================
# Model Cache
# ============================================
_disease_models = {}
_class_indices = {}

# Supported crops and their class label files
SUPPORTED_CROPS = {
    'corn': {'model': 'corn_model.h5', 'indices': 'corn_indices.txt'},
    'potato': {'model': 'potato_model.h5', 'indices': 'potato_indices.txt'},
    'rice': {'model': 'rice_model.h5', 'indices': 'rice_indices.txt'},
    'wheat': {'model': 'wheat_model.h5', 'indices': 'wheat_indices.txt'},
}

# Image preprocessing settings (matching training config)
IMG_SIZE = (224, 224)


def _load_model(crop_type: str):
    """Load a disease detection model and its class indices."""
    crop_type = (crop_type or '').strip()
    artifact = (
        AIModelArtifact.objects.filter(
            operation=AIModelArtifact.Operation.DISEASE_DETECTION,
            crop_type__iexact=crop_type,
            is_active=True,
        )
        .order_by('-updated_at', '-created_at')
        .first()
    )

    if not artifact:
        artifact = (
            AIModelArtifact.objects.filter(
                operation=AIModelArtifact.Operation.DISEASE_DETECTION,
                crop_type__iexact=crop_type,
            )
            .order_by('-is_active', '-updated_at', '-created_at')
            .first()
        )

    if artifact:
        cache_key = f"artifact:{artifact.pk}:{artifact.updated_at.timestamp()}"
        if cache_key in _disease_models:
            return _disease_models[cache_key], _class_indices[cache_key]

        base_dir = Path(settings.BASE_DIR)
        model_path = Path(artifact.model_path) if artifact.model_path else None
        indices_path = Path(artifact.indices_path) if artifact.indices_path else None

        if model_path is None and artifact.model_file:
            model_path = Path(artifact.model_file.path)
        if indices_path is None and artifact.indices_file:
            indices_path = Path(artifact.indices_file.path)

        if model_path is None or indices_path is None:
            raise FileNotFoundError(
                f"Active disease model '{artifact.display_name}' is missing its model or indices file."
            )

        if not model_path.is_absolute():
            model_path = base_dir / model_path
        if not indices_path.is_absolute():
            indices_path = base_dir / indices_path

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not indices_path.exists():
            raise FileNotFoundError(f"Indices file not found: {indices_path}")

        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU
        import tensorflow as tf

        logger.info(f"Loading active disease model '{artifact.display_name}' for {artifact.crop_type} from {model_path}")
        model = tf.keras.models.load_model(str(model_path))

        with open(indices_path, 'r') as f:
            raw = f.read().strip()
            indices = ast.literal_eval(raw)

        reversed_indices = {v: k for k, v in indices.items()}
        _disease_models[cache_key] = model
        _class_indices[cache_key] = reversed_indices
        return model, reversed_indices

    if crop_type in _disease_models:
        return _disease_models[crop_type], _class_indices[crop_type]

    if crop_type not in SUPPORTED_CROPS:
        raise ValueError(f"Unsupported crop type: {crop_type}. Supported: {list(SUPPORTED_CROPS.keys())}")

    model_dir = settings.DISEASE_MODEL_DIR
    crop_config = SUPPORTED_CROPS[crop_type]

    model_path = os.path.join(model_dir, crop_config['model'])
    indices_path = os.path.join(model_dir, crop_config['indices'])

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not os.path.exists(indices_path):
        raise FileNotFoundError(f"Indices file not found: {indices_path}")

    # Lazy import TensorFlow (heavy dependency)
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU
    import tensorflow as tf

    logger.info(f"Loading disease model for {crop_type} from {model_path}")
    model = tf.keras.models.load_model(model_path)

    # Parse class indices from text file
    # Format: {'ClassName': 0, 'ClassName2': 1, ...}
    with open(indices_path, 'r') as f:
        raw = f.read().strip()
        indices = ast.literal_eval(raw)

    # Reverse: {0: 'ClassName', 1: 'ClassName2', ...}
    reversed_indices = {v: k for k, v in indices.items()}

    _disease_models[crop_type] = model
    _class_indices[crop_type] = reversed_indices

    logger.info(f"Loaded {crop_type} model with classes: {list(reversed_indices.values())}")
    return model, reversed_indices


def preprocess_image(image_file) -> np.ndarray:
    """
    Preprocess an uploaded image file for model inference.
    Accepts Django UploadedFile or file-like object.
    """
    img = Image.open(image_file).convert('RGB')
    img = img.resize(IMG_SIZE)
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension
    return img_array


def detect_disease(image_file, crop_type: str) -> dict:
    """
    Run disease detection on an uploaded image.
    
    Args:
        image_file: Django UploadedFile or file-like object
        crop_type: One of 'corn', 'potato', 'rice', 'wheat'
    
    Returns:
        dict with keys: predicted_class, confidence, all_predictions, crop_type
    """
    crop_type = crop_type.lower().strip()
    model, class_labels = _load_model(crop_type)

    # Preprocess
    img_array = preprocess_image(image_file)

    # Predict
    predictions = model.predict(img_array, verbose=0)
    scores = predictions[0]

    # Get top prediction
    predicted_idx = int(np.argmax(scores))
    confidence = float(np.max(scores) * 100)
    predicted_class = class_labels.get(predicted_idx, f"Unknown_{predicted_idx}")

    # Build all predictions sorted by confidence
    all_preds = {}
    for idx, score in enumerate(scores):
        class_name = class_labels.get(idx, f"Unknown_{idx}")
        all_preds[class_name] = round(float(score) * 100, 2)
    all_preds = dict(sorted(all_preds.items(), key=lambda x: x[1], reverse=True))

    # Format class name for display
    display_name = predicted_class.replace('___', ' — ').replace('_', ' ')

    result = {
        'crop_type': crop_type,
        'predicted_class': predicted_class,
        'display_name': display_name,
        'confidence': round(confidence, 2),
        'all_predictions': all_preds,
        'is_healthy': 'healthy' in predicted_class.lower(),
    }

    logger.info(f"Disease detection: {display_name} ({confidence:.1f}%)")
    return result


def get_supported_crops() -> list:
    """Return list of supported crop types."""
    return list(SUPPORTED_CROPS.keys())
