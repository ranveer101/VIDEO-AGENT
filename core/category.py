from transformers import pipeline

# Loads once, reused across calls
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

CATEGORIES = [
    "Technology",
    "Education",
    "Business",
    "Finance",
    "Healthcare",
    "Entertainment",
    "Sports",
    "Science"
]

def classify_video(transcript: str) -> dict:
    if not transcript or not transcript.strip():
        raise ValueError("Transcript is empty")

    result = classifier(
        transcript[:3000],  # BART has token limit
        CATEGORIES
    )

    top_label = result["labels"][0]
    top_score = result["scores"][0]

    return {
    "label": top_label,
    "confidence": round(top_score * 100, 2)
}