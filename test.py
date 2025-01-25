import requests

def save_youtube_html(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(response.text)
        print(f"HTML content saved to {filename}")
    else:
        print(f"Failed to fetch the HTML content. Status code: {response.status_code}")

# Example usage
youtube_url = 'https://www.youtube.com/watch?v=QDuINnRXqt8'
output_filename = 'youtube_page.html'

save_youtube_html(youtube_url, output_filename)
