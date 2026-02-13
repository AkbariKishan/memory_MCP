"""
Test script to verify Ollama API connectivity
"""
import requests
import json

def test_ollama_connection():
    """Test basic Ollama API connectivity"""
    try:
        # Test if Ollama is running
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json()
            print("✓ Ollama is running")
            print(f"✓ Available models: {len(models.get('models', []))}")
            for model in models.get('models', []):
                print(f"  - {model['name']}")
            return True
        else:
            print("✗ Ollama API returned unexpected status:", response.status_code)
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to Ollama. Is it running?")
        print("  Try: ollama serve")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_ollama_inference():
    """Test a simple inference call"""
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3.2:3b",
            "prompt": "Say 'Hello' in one word.",
            "stream": False
        }
        
        print("\nTesting inference with llama3.2:3b...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Inference successful")
            print(f"  Response: {result.get('response', '').strip()}")
            return True
        else:
            print(f"✗ Inference failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Inference error: {e}")
        return False

if __name__ == "__main__":
    print("=== Ollama Connectivity Test ===\n")
    
    if test_ollama_connection():
        test_ollama_inference()
    
    print("\n=== Test Complete ===")
