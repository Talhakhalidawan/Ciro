import os
import json
from django.conf import settings
from groq import Groq
import google.generativeai as genai

def get_groq_key():
    try:
        return getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API_KEY', None)
    except Exception:
        return os.environ.get('GROQ_API_KEY', None)

def get_gemini_key():
    try:
        return getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY', None)
    except Exception:
        return os.environ.get('GEMINI_API_KEY', None)

def ask_ai(prompt: str, system_instruction: str = None, response_json: bool = False) -> str:
    """
    Modularized interface to directly and easily call AI.
    Uses Groq (Llama 3.3 70B) as the primary engine and falls back to Gemini (Gemini 2.5 Flash Lite)
    if Groq is unconfigured or fails.
    
    Args:
        prompt (str): The prompt message to send to the AI.
        system_instruction (str, optional): Instruction to set system role/behavior.
        response_json (bool, optional): Force output formatting as a JSON object.
        
    Returns:
        str: Raw text content from the AI response.
    """
    groq_key = get_groq_key()
    gemini_key = get_gemini_key()
    
    # 1. Try Groq (Primary)
    if groq_key:
        try:
            print("Querying Groq AI...")
            client = Groq(api_key=groq_key)
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            params = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.3,
            }
            if response_json:
                params["response_format"] = {"type": "json_object"}
                
            completion = client.chat.completions.create(**params)
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API call failed: {e}. Trying Gemini fallback...")
            
    # 2. Try Gemini (Fallback)
    if gemini_key:
        try:
            print("Querying Gemini AI...")
            genai.configure(api_key=gemini_key)
            model_name = "gemini-2.5-flash-lite"
            
            generation_config = {}
            if response_json:
                generation_config["response_mime_type"] = "application/json"
                generation_config["temperature"] = 0.3
                
            if system_instruction:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction
                )
            else:
                model = genai.GenerativeModel(model_name=model_name)
                
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**generation_config) if generation_config else None
            )
            return response.text
        except Exception as e:
            print(f"Gemini API call failed: {e}")
            raise RuntimeError(f"AI call failed on both Groq and Gemini. Error: {e}")
            
    raise RuntimeError("No Groq or Gemini API keys configured. Set GROQ_API_KEY or GEMINI_API_KEY in environment/.env file.")
