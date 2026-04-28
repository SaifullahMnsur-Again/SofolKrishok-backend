"""
Soil Type Classification Service
==================================

Loads the pre-trained CNN model for soil type classification.
Classifies soil images into 11 types (e.g., Alluvial, Black, Clayey, etc.).
"""

import os
import logging
import numpy as np
from PIL import Image
from django.conf import settings
from .models import AIModelArtifact

logger = logging.getLogger(__name__)

# ============================================
# Model Cache
# ============================================
_soil_model = None
_soil_model_cache_key = None

# Soil type classes (from the training script README)
SOIL_CLASSES = {
    0: 'Alluvial Soil',
    1: 'Black Soil',
    2: 'Cinder Soil',
    3: 'Clayey Soil',
    4: 'Laterite Soil',
    5: 'Loamy Soil',
    6: 'Peat Soil',
    7: 'Sandy Loam',
    8: 'Sandy Soil',
    9: 'Yellow Soil',
}

IMG_SIZE = (224, 224)


def _load_model():
    """Load the soil classification model."""
    global _soil_model, _soil_model_cache_key
    from pathlib import Path

    artifact = (
        AIModelArtifact.objects.filter(
            operation=AIModelArtifact.Operation.SOIL_CLASSIFICATION,
            is_active=True,
        )
        .order_by('-updated_at', '-created_at')
        .first()
    )

    if artifact:
        cache_key = f"artifact:{artifact.pk}:{artifact.updated_at.timestamp()}"
        if _soil_model is not None and _soil_model_cache_key == cache_key:
            return _soil_model

        # Try relative path first (new hub flow), then legacy field
        model_path_to_load = None
        if artifact.model_path:
            model_path_to_load = Path(settings.BASE_DIR) / artifact.model_path
        elif artifact.model_file:
            model_path_to_load = artifact.model_file.path
        
        if not model_path_to_load or not os.path.exists(model_path_to_load):
            raise FileNotFoundError(
                f"Active soil model '{artifact.display_name}' is missing its model file."
            )

        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU
        import tensorflow as tf

        logger.info(f"Loading active soil model '{artifact.display_name}' from {model_path_to_load}")
        _soil_model = tf.keras.models.load_model(str(model_path_to_load))
        _soil_model_cache_key = cache_key
        return _soil_model

    if _soil_model is not None:
        return _soil_model

    model_path = settings.SOIL_MODEL_PATH

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Soil model not found: {model_path}")

    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU
    import tensorflow as tf

    logger.info(f"Loading soil classifier from {model_path}")
    _soil_model = tf.keras.models.load_model(model_path)
    logger.info(f"Soil classifier loaded successfully")

    return _soil_model


def preprocess_image(image_file) -> np.ndarray:
    """Preprocess an uploaded image for soil classification."""
    img = Image.open(image_file).convert('RGB')
    img = img.resize(IMG_SIZE)
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


def classify_soil(image_file) -> dict:
    """
    Classify soil type from an uploaded image.
    
    Args:
        image_file: Django UploadedFile or file-like object
    
    Returns:
        dict with keys: predicted_type, confidence, all_predictions
    """
    model = _load_model()

    img_array = preprocess_image(image_file)

    predictions = model.predict(img_array, verbose=0)
    scores = predictions[0]

    predicted_idx = int(np.argmax(scores))
    confidence = float(np.max(scores) * 100)
    predicted_type = SOIL_CLASSES.get(predicted_idx, f"Unknown Type {predicted_idx}")

    # All predictions sorted by confidence
    all_preds = {}
    for idx, score in enumerate(scores):
        soil_name = SOIL_CLASSES.get(idx, f"Type_{idx}")
        all_preds[soil_name] = round(float(score) * 100, 2)
    all_preds = dict(sorted(all_preds.items(), key=lambda x: x[1], reverse=True))

    result = {
        'predicted_type': predicted_type,
        'confidence': round(confidence, 2),
        'all_predictions': all_preds,
    }

    logger.info(f"Soil classification: {predicted_type} ({confidence:.1f}%)")
    return result
