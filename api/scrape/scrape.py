import requests
from bs4 import BeautifulSoup
import openai
import json

def truncate_text(text, max_tokens):
    """ Truncate text to fit within the max token limit. """
    # Rough approximation: 1 token ~ 4 characters for English text
    approx_token_length = len(text) // 4
    if approx_token_length <= max_tokens:
        return text
    # Truncate the text to the max token length * 4 to be conservative
    truncated_text = text[:max_tokens * 4]
    return truncated_text

def handler(request):
    data = request.json()
    url = data['url']
    api_key = data['api_key']
    prompt = data['prompt']

    try:
        # Scrape the URL
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        # Setup OpenAI API
        openai.api_key = api_key

        # Calculate remaining tokens for the prompt
        max_tokens = 4096
        prompt_tokens = len(prompt) // 4  # Approximation
        reserved_response_tokens = 1000  # Reserve 1000 tokens for response
        remaining_tokens = max_tokens - prompt_tokens - reserved_response_tokens

        # Truncate HTML content if necessary
        truncated_html_content = truncate_text(html_content, remaining_tokens)

        # Send HTML content and prompt to OpenAI API
        openai_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that helps with web scraping. You will be provided with HTML content and Scraping Logic. Parse the HTML using the Scraping Logic and return the results."},
                {"role": "user", "content": f"HTML Content:\n\n{truncated_html_content}\n\n-----\n\nScraping Logic:\n\n{prompt}"}
            ],
            max_tokens=reserved_response_tokens,  # Tokens reserved for response
            response_format={ "type": "json_object" },
        )

        result = openai_response.choices[0].message.content
        
        return {
            "statusCode": 200,
            "body": json.dumps({"result": result})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
