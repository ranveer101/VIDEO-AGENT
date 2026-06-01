from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from core.llm import get_llm



def build_chain(system_prompt : str):
    llm = get_llm(temperature=0.2)
    return (
        RunnablePassthrough() | RunnableLambda(lambda x : {"text" : x}) |ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human","{text}"),
    ]) | llm |StrOutputParser()
    )

def extract_action_items(transcript:str)->str:
    chain = build_chain(
         "You are an expert meeting analyst. From the meeting transcript, "
        "extract all action items. For each provide:\n"
        "- Task description\n"
        "- Owner (who is responsible)\n"
        "- Deadline (if mentioned, else write 'Not specified')\n\n"
        "Format as a numbered list. If none found say 'No action items found.'"
    )

    return chain.invoke(transcript)


def extract_key_decisions(transcript: str) -> str:
    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all key decisions made. Format as a numbered list. "
        "If none found say 'No key decisions found.'"
    )
    return chain.invoke(transcript)


def extract_questions(transcript: str) -> str:
    chain = build_chain(
        "From the meeting transcript, extract all unresolved questions "
        "or topics needing follow-up. Format as a numbered list. "
        "If none found say 'No open questions found.'"
    )
    return chain.invoke(transcript)


def extract_general_insights(transcript: str) -> dict:
    overview_chain = build_chain(
        "You are an expert video analyst. Extract the most important points from "
        "this video transcript. Format as a concise numbered list."
    )
    takeaways_chain = build_chain(
        "From this video transcript, extract practical takeaways, lessons, or "
        "recommendations. Format as a numbered list. If none are present, say "
        "'No practical takeaways found.'"
    )
    highlights_chain = build_chain(
        "From this video transcript, extract memorable highlights, facts, examples, "
        "or claims. Format as a numbered list. If none are present, say "
        "'No notable highlights found.'"
    )

    return {
        "key_points": overview_chain.invoke(transcript),
        "takeaways": takeaways_chain.invoke(transcript),
        "highlights": highlights_chain.invoke(transcript),
    }
