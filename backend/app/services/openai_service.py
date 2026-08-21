from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)
client = OpenAI()


def generate_reply(
    question: str,
    whiteboard_context: str,
) -> str:

    response = client.responses.create(
        model="gpt-5.6-terra",
        input=f"""
You are an assistant integrated into Excalidraw.

The user asked:
{question}

The current whiteboard analysis is:
{whiteboard_context}

Answer the user's question using the whiteboard context when relevant.
""",
    )

    return response.output_text