import requests
import os

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-2"
HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}

def change_clothes(prompt):
    payload = {
        "inputs": prompt
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
        with open("output.png", "wb") as f:
            f.write(response.content)
        return True
    else:
        print(response.text)
        return False