import os
import base64
import requests


class LLM:
    def __init__(self, model_name: str = 'gpt-5-chat', max_retry: int = 3, temperature: float = 0.0):
        self.model_name = model_name
        self.max_retry = max_retry
        self.temperature = temperature
        self.base_url = self.get_base_url()
        self.api_key = os.environ['OPENAI_API_KEY']

    def get_base_url(self):
        if 'OPENAI_API_URL' not in os.environ:
            raise RuntimeError('OpenAI API URL not set.')
        base_url = os.environ['OPENAI_API_URL']
        if not base_url.endswith('/chat/completions'):
            return f"{base_url}/chat/completions"
        return base_url

    def encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def query(self, prompt):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=data
        )

        if response.status_code != 200:
            print(f"LLM API call failed: {response.status_code} - {response.text}")
            return None

        result = response.json()
        response_text = result["choices"][0]["message"]["content"]
        
        return response_text


if __name__ == "__main__":
    llm = LLM()
    print(llm.query("你是谁?谁开发的你？"))