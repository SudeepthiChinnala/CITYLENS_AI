import importlib
import threading
from typing import Dict

# Lazy import heavy libraries to avoid import-time failures
def _load_dependencies():
    try:
        torch = importlib.import_module('torch')
        from PIL import Image  # Pillow is lightweight
        from transformers import CLIPProcessor, CLIPModel
        return torch, Image, CLIPProcessor, CLIPModel
    except Exception as e:
        # Log or print the error for debugging
        print(f'AI service dependency load failed: {e}')
        return None, None, None, None

CATEGORIES = ['Pothole', 'Garbage', 'Streetlight', 'Damaged Road', 'Drainage', 'Other']

# Keep application startup independent of optional model downloads. Load the
# classifier on first image analysis; unavailable dependencies or weights use
# the existing deterministic fallback response.
_torch = _Image = _CLIPProcessor = _CLIPModel = None
model = processor = None
_model_load_attempted = False
_model_load_lock = threading.Lock()


def _ensure_model_loaded() -> bool:
    global _torch, _Image, _CLIPProcessor, _CLIPModel
    global model, processor, _model_load_attempted
    if model is not None and processor is not None:
        return True
    with _model_load_lock:
        if model is not None and processor is not None:
            return True
        if _model_load_attempted:
            return False
        _model_load_attempted = True
        _torch, _Image, _CLIPProcessor, _CLIPModel = _load_dependencies()
        if not (_torch and _Image and _CLIPProcessor and _CLIPModel):
            return False
        try:
            loaded_model = _CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
            loaded_processor = _CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
        except Exception as e:
            print(f'AI classifier model load failed; using fallback: {e}')
            model = processor = None
            return False
        model, processor = loaded_model, loaded_processor
        return True

def analyze_image(image_path: str) -> Dict:
    """Analyze an image and return problem type, confidence, severity.
    If heavy AI dependencies are unavailable, falls back to a stub response.
    """
    if not _ensure_model_loaded():
        return {
            'problem_type': 'Other',
            'confidence': 0.0,
            'severity': 'LOW',
        }
    Image = _Image
    torch = _torch
    image = Image.open(image_path).convert('RGB')
    inputs = processor(text=CATEGORIES, images=image, return_tensors='pt', padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits_per_image
        probs = logits.softmax(dim=1).cpu().numpy()[0]
    best_idx = probs.argmax()
    confidence = float(probs[best_idx])
    problem = CATEGORIES[best_idx]
    if confidence > 0.85:
        severity = 'HIGH'
    elif confidence > 0.6:
        severity = 'MEDIUM'
    else:
        severity = 'LOW'
    return {'problem_type': problem, 'confidence': confidence, 'severity': severity}
