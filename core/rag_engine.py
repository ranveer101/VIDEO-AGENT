from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from core.llm import get_llm
from core.vector_store import build_vector_store, get_retriever, load_vector_store, new_collection_name


def format_docs(docs):
    return "\n\n".join([doc.page_content for doc in docs])


def _prompt_for(content_type: str, title: str = "", summary: str = ""):
    label = "meeting transcript" if content_type.lower() == "meeting" else "video transcript"
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are Video Mind, a transcript-grounded assistant.

You must answer ONLY from the CURRENT {label}. Do not use prior videos, general memory, or assumptions.

Reply in one short line only, maximum 25 words. Do not include markdown, headings, "retrieved context", transcript excerpts, or bullet points.

Current title:
{title}

Current summary:
{summary}

Retrieved context from the CURRENT transcript:
{{context}}

If the answer is not present in the current transcript context, say exactly:
"I could not find this information in the current transcript."

For broad questions like "what is this video about?", answer in one simple sentence under 25 words.""",
            ),
            ("human", "{question}"),
        ]
    )


def build_rag_chain(
    transcript: str,
    content_type: str = "meeting",
    title: str = "",
    summary: str = "",
    collection_name: str | None = None,
):
    collection = collection_name or new_collection_name()
    vector_store = build_vector_store(transcript, collection_name=collection)
    retriever = get_retriever(vector_store, k=6)
    llm = get_llm(temperature=0.15)

    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | _prompt_for(content_type, title=title, summary=summary)
        | llm
        | StrOutputParser()
    )
    return rag_chain, collection


def load_rag_chain(collection_name: str, content_type: str = "meeting", title: str = "", summary: str = ""):
    vector_store = load_vector_store(collection_name)
    retriever = get_retriever(vector_store)
    llm = get_llm(temperature=0.15)

    return (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | _prompt_for(content_type, title=title, summary=summary)
        | llm
        | StrOutputParser()
    )


def ask_question(rag_chain, question: str) -> str:
    print(f"Question: {question}")
    answer = rag_chain.invoke(question)
    answer = " ".join(str(answer).replace("*", "").split())
    words = answer.split()
    if len(words) > 25:
        answer = " ".join(words[:25]).rstrip(".,;:") + "."
    print(f"Answer: {answer}")
    return answer
