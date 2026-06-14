
import sys


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from collections.abc import Callable
from dotenv import load_dotenv
from core.category import classify_video

from core.extractor import (
    extract_action_items,
    extract_general_insights,
    extract_key_decisions,
    extract_questions,
)
from core.rag_engine import ask_question, build_rag_chain
from core.summarizer import generate_title, summarize
from core.transcriber import transcribe_all
from utils.audio_processor import process_input


load_dotenv()

ProgressCallback = Callable[[str, str, int], None]


def _progress(callback: ProgressCallback | None, stage: str, detail: str, percent: int) -> None:
    if callback:
        callback(stage, detail, percent)


def run_pipeline(
    source: str,
    language: str = "english",
    content_type: str = "meeting",
    progress_callback: ProgressCallback | None = None,
) -> dict:
    print("Starting Video Mind pipeline")

    _progress(progress_callback, "extracting", "Extracting clean audio from the source.", 18)
    chunks, generated_files = process_input(source)

    _progress(progress_callback, "transcribing", "Transcribing content with the selected language engine.", 38)
    transcript = transcribe_all(chunks, language)
    print(f"Raw transcription preview: {transcript[:300]}")

    _progress(progress_callback, "analyzing", "Understanding transcript structure and context.", 56)
    title = generate_title(transcript, content_type=content_type)
    summary = summarize(transcript, content_type=content_type)

    category = classify_video(transcript)
 
    print("Category:", category)
 
    

      

    _progress(progress_callback, "insights", "Generating structured insights and output sections.", 72)
    result = {
    "title": title,
    "transcript": transcript,
    "summary": summary,
    "category": category,
    "content_type": content_type,
    "generated_files": generated_files,
}

    if content_type.lower() == "meeting":
        result.update(
            {
                "action_items": extract_action_items(transcript),
                "key_decisions": extract_key_decisions(transcript),
                "open_questions": extract_questions(transcript),
            }
        )
    else:
        result.update(extract_general_insights(transcript))

    _progress(progress_callback, "saving", "Building the searchable transcript memory.", 88)
    rag_chain, collection_name = build_rag_chain(
        transcript,
        content_type=content_type,
        title=title,
        summary=summary,
    )
    result["rag_chain"] = rag_chain
    result["collection_name"] = collection_name

    _progress(progress_callback, "complete", "Analysis complete.", 100)
    return result


if __name__ == "__main__":
    source = input("Enter YouTube URL or local file path: ").strip()
    language = input("Language (english/hinglish): ").strip() or "english"
    content_type = input("Type (meeting/general): ").strip() or "meeting"
    result = run_pipeline(source, language, content_type)

    print("\n" + "=" * 60)
    print(f"Title: {result['title']}")
    print(f"\nSummary:\n{result['summary']}")

    if content_type == "meeting":
        print(f"\nAction Items:\n{result['action_items']}")
        print(f"\nKey Decisions:\n{result['key_decisions']}")
        print(f"\nOpen Questions:\n{result['open_questions']}")
    else:
        print(f"\nKey Points:\n{result['key_points']}")
        print(f"\nTakeaways:\n{result['takeaways']}")
        print(f"\nHighlights:\n{result['highlights']}")

    print("=" * 60)

    rag_chain = result["rag_chain"]
    while True:
        question = input("You: ").strip()
        if question.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break
        if question:
            print(f"\nAssistant: {ask_question(rag_chain, question)}\n")
