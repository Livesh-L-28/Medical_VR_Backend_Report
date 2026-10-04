import json
import logging
from typing import Dict, Any, Optional, Tuple
import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


class MedicalLLMClientError(Exception):
    """Base exception for Medical LLM Client issues."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: str = "CLIENT_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class MedicalLLMClient:
    """
    Dedicated HTTP Client for communicating with the separate Medical LLM service.
    
    Supports:
    - Configurable URL, endpoint, and timeout via settings/environment
    - Connection error handling
    - Timeout handling
    - Non-200 HTTP status code handling
    - Response parsing and extraction
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout: Optional[int] = None,
        model_name: Optional[str] = None
    ):
        self.base_url = (base_url or settings.MEDICAL_LLM_URL).rstrip("/")
        self.endpoint = endpoint or settings.MEDICAL_LLM_ENDPOINT
        self.timeout = float(timeout or settings.MEDICAL_LLM_TIMEOUT)
        self.model_name = model_name or settings.MEDICAL_LLM_MODEL

    @property
    def target_url(self) -> str:
        endpoint = self.endpoint if self.endpoint.startswith("/") else f"/{self.endpoint}"
        return f"{self.base_url}{endpoint}"

    async def send_evidence_payload(
        self,
        prompt: str,
        structured_evidence: Dict[str, Any],
        model_name: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Send evidence prompt to Medical LLM API.
        
        Returns:
            Tuple[raw_response_text: str, model_name_used: str]
        
        Raises:
            MedicalLLMClientError: On timeout, connection failure, or HTTP error.
        """
        target_model = model_name or self.model_name

        # Determine payload based on external endpoint format
        if self.endpoint == "/generate":
            payload = {
                "prompt": prompt,
                "max_new_tokens": 512,
                "temperature": 0.2
            }
        else:
            # Default /ask endpoint in Medical LLM project
            payload = {
                "question": prompt,
                "model": target_model,
                "top_k_chunks": 2,
                "max_new_tokens": 512,
                "temperature": 0.2
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.target_url, json=payload)
                
                if response.status_code != 200:
                    raise MedicalLLMClientError(
                        message=f"Medical LLM API returned HTTP status {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        error_type="HTTP_ERROR"
                    )

                data = response.json()

                # Extract generated text from response structure
                if isinstance(data, dict):
                    if "answer" in data:
                        raw_text = str(data["answer"])
                    elif "generated_text" in data:
                        raw_text = str(data["generated_text"])
                    else:
                        raw_text = json.dumps(data)
                else:
                    raw_text = str(data)

                return raw_text, target_model

        except httpx.ConnectTimeout as e:
            raise MedicalLLMClientError(
                message=f"Connection to Medical LLM server timed out after {self.timeout}s",
                error_type="TIMEOUT"
            ) from e

        except httpx.ReadTimeout as e:
            raise MedicalLLMClientError(
                message=f"Read from Medical LLM server timed out after {self.timeout}s",
                error_type="TIMEOUT"
            ) from e

        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise MedicalLLMClientError(
                message=f"Unable to connect to Medical LLM server at {self.target_url} (server offline or unreachable)",
                error_type="CONNECTION_REFUSED"
            ) from e

        except json.JSONDecodeError as e:
            raise MedicalLLMClientError(
                message=f"Medical LLM server did not return valid JSON: {str(e)}",
                error_type="INVALID_RESPONSE"
            ) from e


# Global client instance
medical_llm_client = MedicalLLMClient()
