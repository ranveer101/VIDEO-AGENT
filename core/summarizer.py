from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from core.llm import get_llm


def split_transcript(transcript: str) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = 3000,
        chunk_overlap = 200
    )

    return splitter.split_text(transcript)

def summarize(transcript : str, content_type: str = "meeting") -> str:
    llm = get_llm(temperature=0.3)
    is_meeting = content_type.lower() == "meeting"
    map_instruction = (
        "Summarize this portion of a meeting transcript concisely."
        if is_meeting
        else "Summarize this portion of a video transcript concisely, focusing on the core ideas."
    )

    map_prompt = ChatPromptTemplate.from_messages(
        [
        ("system", map_instruction),
        ("human", "{text}"),
    ]
    )

    map_chain = map_prompt | llm | StrOutputParser()

    chunks = split_transcript(transcript)

    chunk_summaries = [map_chain.invoke({"text" : chunk}) for chunk in chunks]

    combined = "\n\n".join(chunk_summaries)

    final_instruction = (
        "You are an expert meeting summarizer. Combine these partial summaries "
        "into one final professional meeting summary in bullet points. Include "
        "context, main discussion themes, outcomes, and next steps when available."
        if is_meeting
        else "You are an expert video analyst. Combine these partial summaries "
        "into a clear, structured video summary in bullet points. Include the "
        "topic, key ideas, important examples, and practical takeaways when available."
    )

    combined_prompt = ChatPromptTemplate.from_messages(
        [("system", final_instruction), ("human", "{text}")]
    )

    combined_chain = (
        RunnablePassthrough() | RunnableLambda(lambda x:{"text":x}) | combined_prompt | llm | StrOutputParser()
    )

    return combined_chain.invoke(combined)

def generate_title(transcript : str, content_type: str = "meeting") -> str:
    llm = get_llm(temperature=0.3)
    label = "meeting" if content_type.lower() == "meeting" else "video"


    title_chain = (
        RunnablePassthrough() | RunnableLambda(lambda x:{"text":x}) | 
        ChatPromptTemplate.from_messages([
             (
                "system",
                f"Based on the {label} transcript, generate a short professional title "
                "(max 8 words). Only return the title, nothing else.",
            ),
            ("human", "{text}"),
        ])
        | llm
        |StrOutputParser()
    )

    return title_chain.invoke(transcript[:2000])


