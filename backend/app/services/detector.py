import torch
from PIL import Image
from transformers import (
    AutoProcessor,
    AutoModelForZeroShotObjectDetection,
)

MODEL_ID = "IDEA-Research/grounding-dino-tiny"

DEVICE = (
    "cuda:0"
    if torch.cuda.is_available()
    else "cpu"
)

processor = AutoProcessor.from_pretrained(MODEL_ID)

model = (
    AutoModelForZeroShotObjectDetection
    .from_pretrained(MODEL_ID)
    .to(DEVICE)
)

model.eval()


def detect_target(
    image_path: str,
    target_description: str,
) -> list[dict]:

    image = Image.open(image_path).convert("RGB")

    inputs = processor(
        images=image,
        text=[[target_description]],
        return_tensors="pt",
    ).to(DEVICE)

    with torch.no_grad():
        outputs = model(**inputs)

    result = (
        processor
        .post_process_grounded_object_detection(
            outputs,
            threshold=0.25,
            text_threshold=0.20,
            target_sizes=[
                (image.height, image.width)
            ],
        )[0]
    )

    detections = []

    for box, score, label in zip(
        result["boxes"],
        result["scores"],
        result["text_labels"],
    ):
        detections.append({
            "bbox": [
                round(v, 2)
                for v in box.tolist()
            ],
            "score": round(
                score.item(),
                4,
            ),
            "label": label,
        })

    return detections