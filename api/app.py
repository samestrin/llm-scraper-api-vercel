from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import requests
import openai
import json
from bs4 import BeautifulSoup
import re
from json_repair import repair_json

from gptcache import cache
from gptcache.adapter import openai

cache.init()
cache.set_openai_key()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

model = "gpt-4o"
max_tokens = 75000
reserved_response_tokens = 500

def estimate_tokens(text):
    """Estimate the number of tokens based on word count."""
    return len(text.split())

def truncate_text(text, max_tokens):
    words = text.split()
    if len(words) <= max_tokens:
        return text
    truncated_words = words[:max_tokens]
    return ' '.join(truncated_words)

def clean_text(text):
    soup = BeautifulSoup(text, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text()
    return re.sub(r'\n+', '\n', text).strip()

def cleanup_json_response(json_block, api_key):
    # Define a safe regex pattern to extract JSON content
    pattern = re.compile(r'json\s*({.*})', re.DOTALL)

    # Search for the pattern in the json_block
    match = pattern.search(json_block)
    
    # If a match is found, update the json_block to the captured group
    if match:
        json_block = match.group(1)

    prompt = f'Consider the provided block of "JSON" carefully. Please correct it and create a valid JSON object.\n\n-----\n\nJSON:\n\n{json_block}\n\n-----\n\nRestriction: You must return a valid JSON object, there is no limit to this response.\n\n'

    try:
        openai.api_key = api_key
        openai_response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an assistant that helps correct JSON objects."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=reserved_response_tokens,
        )
        result = openai_response['choices'][0]['message']['content'].strip()
        repaired_json = repair_json(result)

        # Search for the pattern in the json_block
        match = pattern.search(repaired_json)
        
        # If a match is found, update the json_block to the captured group
        if match:
            repaired_json = match.group(1)

        return repaired_json
    except openai.error.OpenAIError as e:
        return f"OpenAI API error: {str(e)}"

def process_chunk(content, prompt, api_key, reserved_response_tokens, max_tokens, is_html):
    prompt_token_count = estimate_tokens(f"{prompt} {content}")
    chunk_size = (max_tokens - prompt_token_count - reserved_response_tokens) // 2
    words = content.split()
    results = []
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i + chunk_size])
        chunk_prompt = f"{'HTML' if is_html else 'Text'} Content Chunk:\n\n{chunk}\n\n-----\n\nScraping Logic:\n\n{prompt}\n\nRestriction:\n\nIf you have matches based on the Scraping Logic, build the results json, logically creating keys for the extracted values. If you do not have any matches, return an empty json object."
        try:
            openai.api_key = api_key
            openai_response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an assistant that helps with web scraping. You will be provided with {'HTML' if is_html else 'text'} content chunks and Scraping Logic. Parse the {'HTML' if is_html else 'text'} content chunks using the Scraping Logic and return the results. If you do not have any matches, return an empty json object."},
                    {"role": "user", "content": chunk_prompt}
                ],
                max_tokens=reserved_response_tokens,
            )
            result = openai_response['choices'][0]['message']['content'].strip()
            results.append(result)
        except openai.error.OpenAIError as e:
            return f"OpenAI API error: {str(e)}"
    return "\n".join(results)

def process_full(content, prompt, api_key, reserved_response_tokens, max_tokens, is_html):
    prompt_token_count = estimate_tokens(f"{prompt} {content}")
    full_prompt = f"{'HTML' if is_html else 'Text'} Content:\n\n{content}\n\n-----\n\nScraping Logic:\n\n{prompt}\n\nRestriction:\n\nIf you have matches based on the Scraping Logic, build the results json, logically creating keys for the extracted values. If you do not have any matches, return an empty json object."
    try:
        openai.api_key = api_key
        openai_response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": f"You are an assistant that helps with web scraping. You will be provided with {'HTML' if is_html else 'text'} content and Scraping Logic. Parse the {'HTML' if is_html else 'text'} content chunks using the Scraping Logic and return the results. If you do not have any matches, return an empty json object."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=reserved_response_tokens,
        )
        return openai_response['choices'][0]['message']['content'].strip()
    except openai.error.OpenAIError as e:
        return f"OpenAI API error: {str(e)}"

@app.route('/api/scrape', methods=['POST'])
@cross_origin()  # Explicitly enable CORS for this endpoint
def scrape():
    try:
        url = request.form.get('url')
        api_key = request.form.get('api_key')
        prompt = request.form.get('prompt')
        mode = request.form.get('mode', 'HTML').upper()

        if not url or not api_key or not prompt:
            raise ValueError("Missing required form parameters: url, api_key, or prompt")

        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        if mode == 'HTML':
            if estimate_tokens(f"{prompt} {html_content}") <= max_tokens - reserved_response_tokens:
                result = process_full(html_content, prompt, api_key, reserved_response_tokens, max_tokens, is_html=True)
            else:
                result = process_chunk(html_content, prompt, api_key, reserved_response_tokens, max_tokens, is_html=True)
        elif mode == 'TEXT':
            cleaned_content = clean_text(html_content)
            if estimate_tokens(f"{prompt} {cleaned_content}") <= max_tokens - reserved_response_tokens:
                result = process_full(cleaned_content, prompt, api_key, reserved_response_tokens, max_tokens, is_html=False)
            else:
                result = process_chunk(cleaned_content, prompt, api_key, reserved_response_tokens, max_tokens, is_html=False)
        else:
            raise ValueError("Unsupported mode")

        if "OpenAI API error" in result:
            raise Exception(result)

        result = cleanup_json_response(result, api_key)

        return jsonify({"result": result})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"HTTP request error: {str(e)}"}), 500
    except openai.error.OpenAIError as e:
        return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"General error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
