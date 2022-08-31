import requests


def check_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0',
        'Accept-Language': 'en-GB,en;q=0.5',
        'Referer': 'https://www.wikipedia.org',
        'DNT': '1'
    }
    try:
        response = requests.head(url, headers=headers, allow_redirects=True)
    except requests.exceptions.RequestException:
        return False
    else:
        if response.status_code == 405:
            response = requests.get(url, headers=headers, allow_redirects=True)
        return response.status_code == 200


def check_source_urls(params):
    pass
