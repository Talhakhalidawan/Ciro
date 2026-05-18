import os
import json
from django.conf import settings
from groq import Groq
import google.generativeai as genai
from openai import OpenAI
from mistralai.client import Mistral

def get_key(key_name):
    """
    Safely retrieves the specified API key from settings or environment variables.
    """
    try:
        return getattr(settings, key_name, None) or os.environ.get(key_name, None)
    except Exception:
        return os.environ.get(key_name, None)

def ask_ai(prompt: str, system_instruction: str = None, response_json: bool = False) -> str:
    """
    Highly resilient and multi-provider modularized AI routing engine.
    Sequentially queries the configured providers, trying their best models,
    and automatically falls back to the next provider on failure.
    
    Order of operations:
    1. Groq / Grok (llama-3.3-70b-versatile)
    2. BluesMinds Gateway (gpt-4o, claude-3-5-sonnet)
    3. Gemini (gemini-2.5-flash, gemini-2.5-flash-lite)
    4. Mistral (mistral-large-latest, mistral-small-latest)
    
    Args:
        prompt (str): The main prompt text for generation.
        system_instruction (str, optional): Instruction to guide system role/behavior.
        response_json (bool, optional): Enforce output format as a structured JSON object.
        
    Returns:
        str: Raw text/JSON response content.
    """
    errors = []
    
    # ──────────────────────────────────────────────
    # 1. GEMINI
    # ──────────────────────────────────────────────
    gemini_key = get_key('GEMINI_API_KEY')
    if gemini_key:
        model_candidates = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
        for model_name in model_candidates:
            try:
                print(f"Querying Gemini AI (model: {model_name})...")
                genai.configure(api_key=gemini_key)
                
                generation_config = {}
                if response_json:
                    generation_config["response_mime_type"] = "application/json"
                    generation_config["temperature"] = 0.3
                    
                if system_instruction:
                    model_instance = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_instruction
                    )
                else:
                    model_instance = genai.GenerativeModel(model_name=model_name)
                    
                response = model_instance.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(**generation_config) if generation_config else None
                )
                if response.text:
                    return response.text
            except Exception as e:
                err_msg = f"Gemini ({model_name}) failed: {e}"
                print(err_msg)
                errors.append(err_msg)

    # ──────────────────────────────────────────────
    # 2. GROQ
    # ──────────────────────────────────────────────
    groq_key = get_key('GROQ_API_KEY')
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
            res = completion.choices[0].message.content
            if res:
                return res
        except Exception as e:
            err_msg = f"Groq/Grok failed: {e}"
            print(err_msg)
            errors.append(err_msg)
            
    # ──────────────────────────────────────────────
    # 3. BLUESMINDS
    # ──────────────────────────────────────────────
    bluesminds_key = get_key('BLUESMINDS_API_KEY')
    if bluesminds_key:
        model_candidates = ["gpt-4o", "claude-3-5-sonnet", "meta-llama/llama-3.3-70b-instruct", "llama-3.3-70b"]
        for model in model_candidates:
            try:
                print(f"Querying BluesMinds AI (model: {model})...")
                client = OpenAI(api_key=bluesminds_key, base_url="https://api.bluesminds.com/v1")
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                }
                if response_json:
                    params["response_format"] = {"type": "json_object"}
                    
                completion = client.chat.completions.create(**params)
                res = completion.choices[0].message.content
                if res:
                    return res
            except Exception as e:
                err_msg = f"BluesMinds ({model}) failed: {e}"
                print(err_msg)
                errors.append(err_msg)

    # ──────────────────────────────────────────────
    # 4. MISTRAL
    # ──────────────────────────────────────────────
    mistral_key = get_key('MISTRAL_API_KEY')
    if mistral_key:
        model_candidates = ["mistral-large-latest", "mistral-small-latest", "open-mixtral-8x22b"]
        for model in model_candidates:
            try:
                print(f"Querying Mistral AI (model: {model})...")
                client = Mistral(api_key=mistral_key)
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                params = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                }
                if response_json:
                    params["response_format"] = {"type": "json_object"}
                    
                completion = client.chat.complete(**params)
                res = completion.choices[0].message.content
                if res:
                    return res
            except Exception as e:
                err_msg = f"Mistral ({model}) failed: {e}"
                print(err_msg)
                errors.append(err_msg)

    # ──────────────────────────────────────────────
    # OUT OF OPTIONS
    # ──────────────────────────────────────────────
    raise RuntimeError(f"All configured AI key providers and fallback models failed: {errors}")
