import requests
import json
import logging
import os
from typing import Dict, Optional
import google.generativeai as genai
try:
    from src.memory_mcp.config import config
except ImportError:
    from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonitorAgent:
    """
    Lightweight agent that monitors conversations and classifies messages.
    Decides whether a message contains important information worth extracting.
    """
    
    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or config.get("monitor.provider", "ollama")
        self.model_name = model or config.get("monitor.model", "llama3.2:3b")
        self.ollama_url = config.get("ollama.url", "http://localhost:11434")
        
        if self.provider == "google":
            api_key = config.google_api_key
            if not api_key or api_key == "YOUR_GOOGLE_API_KEY":
                logger.error("Google API Key not found in config or environment")
                # Fallback to Ollama if misconfigured? 
                # Better to warn and proceed with whatever we can.
            else:
                genai.configure(api_key=api_key)
                self.google_model = genai.GenerativeModel(self.model_name)
        
    def _build_classification_prompt(self, message: str, context: Optional[list] = None) -> str:
        """Build the prompt for message classification"""
        prompt = f"""Classify this message for a memory system.

RULES:
1. If the message contains preferences, facts, project details, or decisions → important: true
2. If the message is just greetings, thanks, or chitchat → important: false

Examples:
- "I prefer dark mode" → {{"important": true, "category": "preference", "confidence": 0.95}}
- "This uses FastAPI" → {{"important": true, "category": "project", "confidence": 0.9}}
- "My name is Sarah" → {{"important": true, "category": "fact", "confidence": 1.0}}
- "Hello!" → {{"important": false, "category": "chitchat", "confidence": 1.0}}
- "Thanks" → {{"important": false, "category": "chitchat", "confidence": 1.0}}

Message: "{message}"

Return ONLY valid JSON (no extra text):"""
        
        return prompt
    
    async def classify(self, message: str, context: Optional[list] = None) -> Dict:
        """
        Classify a message as important or not.
        """
        if self.provider == "google":
            return await self._classify_google(message, context)
        else:
            return await self._classify_ollama(message, context)

    async def _classify_google(self, message: str, context: Optional[list] = None) -> Dict:
        """Classify using Google Gemini"""
        try:
            prompt = self._build_classification_prompt(message, context)
            logger.info(f"Classifying message via Gemini: {message[:50]}...")
            
            response = self.google_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    candidate_count=1,
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                classification = json.loads(response.text)
                logger.info(f"Gemini Classification: {classification}")
                return classification
            return self._default_classification()
        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return self._default_classification()

    async def _classify_ollama(self, message: str, context: Optional[list] = None) -> Dict:
        """Classify using Ollama"""
        try:
            prompt = self._build_classification_prompt(message, context)
            api_endpoint = f"{self.ollama_url}/api/generate"
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 100}
            }
            
            logger.info(f"Classifying message via Ollama: {message[:50]}...")
            response = requests.post(api_endpoint, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                return self._parse_json_safe(response_text)
            return self._default_classification()
        except Exception as e:
            logger.error(f"Ollama classification error: {e}")
            return self._default_classification()

    def _parse_json_safe(self, text: str) -> Dict:
        try:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
            return self._default_classification()
        except Exception:
            return self._default_classification()
    
    def _default_classification(self) -> Dict:
        """Return a safe default classification when errors occur"""
        return {
            "important": False,
            "category": "chitchat",
            "confidence": 0.0
        }
    
    def should_extract(self, classification: Dict, threshold: float = 0.6) -> bool:
        """Determine if a message should be sent to the Extraction Agent."""
        return (
            classification.get("important", False) and 
            classification.get("confidence", 0.0) >= threshold
        )


class MonitorAgentSync(MonitorAgent):
    """Synchronous version of MonitorAgent"""
    
    def classify(self, message: str, context: Optional[list] = None) -> Dict:
        # Simple blocking wrapper
        import asyncio
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(super().classify(message, context))
