import os
import json
import logging
from abc import ABC
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):

    def __init__(self, model: str):
        self.model = model

        # Provider order: primary first, fallback second
        self.providers = [
            p.strip().lower()
            for p in os.getenv("LLM_PROVIDERS", "groq").split(",")
            if p.strip()
        ]

        self.clients = {}

    def _get_client(self, provider: str):

        if provider in self.clients:
            return self.clients[provider]

        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")

            if not api_key:
                raise ValueError("GROQ_API_KEY is missing")

            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )

        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                raise ValueError("OPENAI_API_KEY is missing")

            client = OpenAI(api_key=api_key)

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        self.clients[provider] = client

        return client

    def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float = 0.7
    ) -> T:

        schema = (
    response_model.model_json_schema()
    if hasattr(response_model, "model_json_schema")
    else response_model.schema()
)

        system_message = f"""
{system_prompt}

IMPORTANT:
Return only valid JSON.
Do not include markdown code blocks.
Follow this JSON schema exactly:

{json.dumps(schema)}
"""

        errors = []

        for provider in self.providers:

            try:
                client = self._get_client(provider)

                # Groq model and OpenAI model are configured separately.
                if provider == "groq":
                    model = os.getenv(
                        "GROQ_MODEL",
                        "openai/gpt-oss-20b"
                    )
                else:
                    model = self.model

                logger.info(
                    "Generating response using provider=%s model=%s",
                    provider,
                    model
                )

                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_message
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    temperature=temperature,
                    response_format={
                        "type": "json_object"
                    }
                )

                content = response.choices[0].message.content

                if not content:
                    raise ValueError("LLM returned an empty response")

                # Pydantic v2 / v1 compatibility
                if hasattr(response_model, "model_validate_json"):
                    result = response_model.model_validate_json(content)
                else:
                    result = response_model.parse_raw(content)

                logger.info(
                    "Successfully generated response using %s",
                    provider
                )

                return result

            except Exception as e:

                errors.append(f"{provider}: {str(e)}")

                logger.exception(
                    "LLM provider %s failed",
                    provider
                )

        raise RuntimeError(
            "All configured LLM providers failed:\n"
            + "\n".join(errors)
        )