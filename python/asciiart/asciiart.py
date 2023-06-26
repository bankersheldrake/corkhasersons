import requests
from bs4 import BeautifulSoup
import argparse
import asyncio
from pyppeteer import launch

def scrape_text_old(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    response = requests.get(url, headers=headers)    
    soup = BeautifulSoup(response.text, 'html.parser')
    print(soup)
    div_tag = soup.find('div', {'id': 'outputFigDisplay'})
    if not div_tag:
        print("No ASCII art found on the page.")
        return None
    ascii_art = div_tag.text
    return ascii_art



async def scrape_text(url):
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    
    element = await page.querySelector('#outputFigDisplay')
    ascii_art = await page.evaluate('(element) => element.textContent', element)
    
    await browser.close()
    return ascii_art

url = "https://patorjk.com/software/taag/#p=display&h=2&v=1&f=Bloody&t=Orbotnik"
ascii_art = asyncio.get_event_loop().run_until_complete(scrape_text(url))
print(ascii_art)


# def main():
#     parser = argparse.ArgumentParser(description='Scrape ASCII art from a given URL.')
#     parser.add_argument('url', help='The URL to scrape ASCII art from.')

#     args = parser.parse_args()

#     ascii_art = scrape_text(args.url)
#     if ascii_art is not None:
#         print(ascii_art)

# if __name__ == "__main__":
#     main()