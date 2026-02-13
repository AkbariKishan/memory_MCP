import requests
import json
import logging
import os
from typing import Dict, Optional, List
import google.generativeai as genai

try:
    from src.memory_mcp.config import config
except ImportError:
    from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractionAgent:
    """
    Agent that extracts structured facts from messages.
    Takes messages flagged as important by the Monitor Agent and converts them
    into structured fact entries for the memory system.
    """
    
    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or config.get("extraction.provider", "ollama")
        self.model_name = model or config.get("extraction.model", "llama3.1:8b")
        self.ollama_url = config.get("ollama.url", "http://localhost:11434")
        
        if self.provider == "google":
            api_key = config.google_api_key
            if not api_key or api_key == "YOUR_GOOGLE_API_KEY":
                logger.error("Google API Key not found for Extraction Agent")
            else:
                genai.configure(api_key=api_key)
                self.google_model = genai.GenerativeModel(self.model_name)
        
    def _build_extraction_prompt(self, message: str, category: str, context: Optional[List] = None) -> str:
        """Build the prompt for fact extraction"""
        
        context_str = ""
        if context:
            recent = context[-3:]  # Last 3 messages for context
            msgs = []
            for m in recent:
                if isinstance(m, dict):
                    msgs.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
                else:
                    msgs.append(str(m))
            context_str = "\n".join(msgs)
            context_str = f"\n\nRecent conversation context:\n{context_str}\n"
        
        prompt = f"""Extract a structured fact from this message for a long-term memory system.

Message category: {category}
Message: "{message}"{context_str}

Your task:
1. Identify the main topic (e.g., "User Preferences", "Tech Stack", "Personal Info")
2. Extract the key information as a concise statement
3. List any entities mentioned (names, technologies, places, etc.)

Return ONLY valid JSON:
{{
  "topic": "Brief topic name",
  "content": "Clear, concise fact statement",
  "entities": ["entity1", "entity2"],
  "category": "{category}"
}}

Examples:
- "I prefer dark mode" → {{"topic": "UI Preferences", "content": "Prefers dark mode", "entities": ["dark mode"], "category": "preference"}}
- "Project uses FastAPI" → {{"topic": "Tech Stack", "content": "Project uses FastAPI", "entities": ["FastAPI"], "category": "project"}}

JSON response:"""
        
        return prompt
    
    def extract_facts(self, message: str, category: str, context: Optional[List] = None) -> Dict:
        """
        Extract structured facts from a message.
        """
        if self.provider == "google":
            return self._extract_google(message, category, context)
        else:
            return self._extract_ollama(message, category, context)

    def _extract_google(self, message: str, category: str, context: Optional[List] = None) -> Dict:
        """Extract facts using Google Gemini"""
        try:
            prompt = self._build_extraction_prompt(message, category, context)
            logger.info(f"Extracting facts via Gemini: {message[:50]}...")
            
            response = self.google_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    candidate_count=1,
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                extraction = json.loads(response.text)
                return self._validate_extraction(extraction, message, category)
            return self._default_extraction(message, category)
        except Exception as e:
            logger.error(f"Gemini extraction error: {e}")
            return self._default_extraction(message, category)

    def _extract_ollama(self, message: str, category: str, context: Optional[List] = None) -> Dict:
        """Extract facts using Ollama"""
        try:
            prompt = self._build_extraction_prompt(message, category, context)
            api_endpoint = f"{self.ollama_url}/api/generate"
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 200},
                "format": "json"
            }
            
            logger.info(f"Extracting facts via Ollama: {message[:50]}...")
            response = requests.post(api_endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                return self._parse_json_safe(response_text, message, category)
            return self._default_extraction(message, category)
        except Exception as e:
            logger.error(f"Ollama extraction error: {e}")
            return self._default_extraction(message, category)

    async def resolve_conflict(self, new_fact_content: str, existing_fact_content: str) -> str:
        """Use LLM to resolve a conflict between new info and existing knowledge."""
        prompt = f"""CONFLICT DETECTED in User Memory.

Existing Knowledge: "{existing_fact_content}"
New Information: "{new_fact_content}"

Your task:
1. Determine if the new information updates, contradicts, or complements the existing fact.
2. Provide a single unified fact that reconciles both.
3. If they are completely different, favor the newer information but mention the change.

Unified Fact:"""
        
        try:
            if self.provider == "google":
                response = self.google_model.generate_content(prompt)
                return response.text.strip()
            else:
                payload = {"model": self.model_name, "prompt": prompt, "stream": False}
                res = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=30)
                return res.json().get('response', new_fact_content).strip()
        except Exception as e:
            logger.error(f"Resolution error: {e}")
            return new_fact_content

    def _parse_json_safe(self, text: str, message: str, category: str) -> Dict:
        try:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                extraction = json.loads(text[json_start:json_end])
                return self._validate_extraction(extraction, message, category)
            return self._default_extraction(message, category)
        except Exception:
            return self._default_extraction(message, category)

    def _validate_extraction(self, extraction: Dict, message: str, category: str) -> Dict:
        required_fields = ["topic", "content", "entities", "category"]
        if all(field in extraction for field in required_fields):
            return extraction
        return self._default_extraction(message, category)
    
    def _default_extraction(self, message: str, category: str) -> Dict:
        return {
            "topic": "General",
            "content": message,
            "entities": [],
            "category": category
        }
