"""
Extraction Agent - Extracts structured facts from important messages
Uses Llama 3.1 8B for intelligent fact extraction and structuring
"""
import requests
import json
from typing import Dict, Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractionAgent:
    """
    Agent that extracts structured facts from messages.
    Takes messages flagged as important by the Monitor Agent and converts them
    into structured fact entries for the memory system.
    """
    
    def __init__(self, model: str = "llama3.1:8b", ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self.api_endpoint = f"{ollama_url}/api/generate"
        
    def _build_extraction_prompt(self, message: str, category: str, context: Optional[List] = None) -> str:
        """Build the prompt for fact extraction"""
        
        context_str = ""
        if context:
            recent = context[-3:]  # Last 3 messages for context
            context_str = "\n".join([f"- {msg}" for msg in recent])
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
Message: "I prefer dark mode in all my applications"
→ {{"topic": "UI Preferences", "content": "Prefers dark mode in all applications", "entities": ["dark mode"], "category": "preference"}}

Message: "This project uses FastAPI and PostgreSQL"
→ {{"topic": "Tech Stack", "content": "Project uses FastAPI and PostgreSQL", "entities": ["FastAPI", "PostgreSQL"], "category": "project"}}

Message: "My name is Sarah and I work as a data scientist"
→ {{"topic": "Personal Info", "content": "Name is Sarah, works as a data scientist", "entities": ["Sarah", "data scientist"], "category": "fact"}}

JSON response:"""
        
        return prompt
    
    def extract_facts(self, message: str, category: str, context: Optional[List] = None) -> Dict:
        """
        Extract structured facts from a message.
        
        Args:
            message: The message to extract facts from
            category: The category from Monitor Agent (preference, fact, project, etc.)
            context: Optional conversation context
            
        Returns:
            Dict with keys: topic, content, entities, category
        """
        try:
            prompt = self._build_extraction_prompt(message, category, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Low temperature for consistent extraction
                    "num_predict": 200   # Allow for detailed extraction
                }
            }
            
            logger.info(f"Extracting facts from: {message[:50]}...")
            response = requests.post(self.api_endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                
                # Parse JSON response
                try:
                    # Extract JSON from response
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        extraction = json.loads(json_str)
                        
                        # Validate required fields
                        required_fields = ["topic", "content", "entities", "category"]
                        if all(field in extraction for field in required_fields):
                            logger.info(f"Extracted: {extraction['topic']} - {extraction['content']}")
                            return extraction
                        else:
                            logger.warning(f"Missing required fields in extraction: {extraction}")
                            return self._default_extraction(message, category)
                    else:
                        logger.warning(f"No JSON found in response: {response_text}")
                        return self._default_extraction(message, category)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {e}. Response: {response_text}")
                    return self._default_extraction(message, category)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._default_extraction(message, category)
                
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return self._default_extraction(message, category)
    
    def _default_extraction(self, message: str, category: str) -> Dict:
        """Return a safe default extraction when errors occur"""
        return {
            "topic": "General",
            "content": message,
            "entities": [],
            "category": category
        }
    
    def merge_with_existing(self, new_fact: Dict, existing_facts: Dict) -> Dict:
        """
        Merge a new fact with existing facts.
        
        Args:
            new_fact: The newly extracted fact
            existing_facts: The current fact sheet (dict of topic -> content)
            
        Returns:
            Updated fact sheet
        """
        topic = new_fact.get("topic", "General")
        content = new_fact.get("content", "")
        
        if topic in existing_facts:
            # Append to existing topic
            existing_content = existing_facts[topic]
            # Avoid duplicates
            if content not in existing_content:
                existing_facts[topic] = f"{existing_content}; {content}"
        else:
            # New topic
            existing_facts[topic] = content
        
        return existing_facts
