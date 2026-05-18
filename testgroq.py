import os
import django

# Setup Django environment so we can import from our apps
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ciro_django.settings')
try:
    django.setup()
except Exception:
    pass

from api.ai import ask_ai

if __name__ == "__main__":
    print("--- Testing Modular AI Interface ---")
    
    # Make sure GROQ_API_KEY is defined in your .env file or environment!
    # Format in .env:
    # GROQ_API_KEY=gsk_...
    
    try:
        prompt = "Hello! Tell me in 10 words if Llama 3.3 is working on Groq."
        print(f"Sending prompt: '{prompt}'")
        
        response = ask_ai(prompt)
        print("\nAI Response:")
        print(response)
    except Exception as e:
        print(f"\nAI test failed: {e}")
