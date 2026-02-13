"""
Monitor Agent - Classifies message importance in real-time
Uses Llama 3.2 3B for fast, lightweight classification
"""
import requests
import json
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonitorAgent:
    """
    Lightweight agent that monitors conversations and classifies messages.
    Decides whether a message contains important information worth extracting.
    """
    
    def __init__(self, model: str = "llama3.2:3b", ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self.api_endpoint = f"{ollama_url}/api/generate"
        
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
        
        Args:
            message: The message to classify
            context: Optional conversation context (list of previous messages)
            
        Returns:
            Dict with keys: important (bool), category (str), confidence (float)
        """
        try:
            prompt = self._build_classification_prompt(message, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent classification
                    "num_predict": 100   # Short response expected
                }
            }
            
            logger.info(f"Classifying message: {message[:50]}...")
            response = requests.post(self.api_endpoint, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                
                # Parse JSON response
                try:
                    # Extract JSON from response (in case there's extra text)
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        classification = json.loads(json_str)
                        
                        logger.info(f"Classification: {classification}")
                        return classification
                    else:
                        logger.warning(f"No JSON found in response: {response_text}")
                        return self._default_classification()
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {e}. Response: {response_text}")
                    return self._default_classification()
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._default_classification()
                
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return self._default_classification()
    
    def _default_classification(self) -> Dict:
        """Return a safe default classification when errors occur"""
        return {
            "important": False,
            "category": "chitchat",
            "confidence": 0.0
        }
    
    def should_extract(self, classification: Dict, threshold: float = 0.6) -> bool:
        """
        Determine if a message should be sent to the Extraction Agent.
        
        Args:
            classification: The classification dict from classify()
            threshold: Minimum confidence threshold (default 0.6)
            
        Returns:
            True if message should be extracted
        """
        return (
            classification.get("important", False) and 
            classification.get("confidence", 0.0) >= threshold
        )


# Synchronous wrapper for non-async contexts
class MonitorAgentSync(MonitorAgent):
    """Synchronous version of MonitorAgent"""
    
    def classify(self, message: str, context: Optional[list] = None) -> Dict:
        """Synchronous classify method"""
        try:
            prompt = self._build_classification_prompt(message, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 100
                }
            }
            
            logger.info(f"Classifying message: {message[:50]}...")
            response = requests.post(self.api_endpoint, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                
                try:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        classification = json.loads(json_str)
                        logger.info(f"Classification: {classification}")
                        return classification
                    else:
                        return self._default_classification()
                except json.JSONDecodeError:
                    return self._default_classification()
            else:
                return self._default_classification()
                
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return self._default_classification()
