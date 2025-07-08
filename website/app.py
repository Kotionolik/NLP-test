from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import random
import time
import model

app = Flask(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_url():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'DNT': '1'  # Do Not Track
        }

        time.sleep(random.uniform(1.0, 3.0))

        response = requests.get(
            url,
            timeout=15,
            headers=headers,
            cookies={'session': str(random.randint(1000, 9999))}
        )

        if response.status_code != 200:
            return jsonify({
                "error": f"Website returned status {response.status_code}",
                "suggestion": "Try again later or use a different website"
            }), 400

        soup = BeautifulSoup(response.text, 'html.parser')

        text = soup.get_text(separator=' ', strip=True)
        unique_products = model.extract_furniture_names(text)

        return jsonify({
            "products": unique_products,
            "count": len(unique_products)
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": f"Website request failed: {str(e)}",
            "suggestion": "Try a different URL or check if the site allows scraping"
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Processing error: {str(e)}",
            "suggestion": "Try again or contact support"
        }), 500


if __name__ == '__main__':
    app.run(port=5000)