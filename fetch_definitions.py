import json
import re
import requests
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import wordnet
from typing import Dict, List, Optional
import argparse


class DefinitionFetcher:
    _nltk_data_checked = False 
    
    def __init__(self):
        self._ensure_nltk_data()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DefinitionFetcher (https://github.com/tnguyen91/context-aware-WSD)'
        })
    
    @classmethod
    def _ensure_nltk_data(cls):
        if cls._nltk_data_checked:
            return
            
        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            print("Downloading WordNet data...")
            nltk.download('wordnet')
        
        try:
            nltk.data.find('corpora/omw-1.4')
        except LookupError:
            print("Downloading OMW data...")
            nltk.download('omw-1.4')
            
        cls._nltk_data_checked = True
    
    def fetch_easton_definition(self, word: str) -> Optional[str]:
        try:
            url = f"https://www.biblegateway.com/resources/eastons-bible-dictionary/{word.capitalize()}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                content_selectors = [
                    'div.resource-content',
                    'div.content-wrapper', 
                    'div.definition',
                    'div.entry-content',
                    'main',
                    'article'
                ]
                
                content_div = None
                for selector in content_selectors:
                    content_div = soup.select_one(selector)
                    if content_div:
                        break
                
                if not content_div:
                    content_div = soup.find('body')
                
                if content_div:
                    for unwanted in content_div.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                        unwanted.decompose()
                    
                    paragraphs = content_div.find_all('p')
                    for p in paragraphs:
                        ptext = p.get_text(separator=' ', strip=True)
                        if ptext and len(ptext) > 30:
                            text = re.sub(r'\s+', ' ', ptext).strip()
                            text = re.sub(r'BibleGateway\.com.*$', '', text)
                            text = re.sub(r'Copyright.*$', '', text)
                            text = re.sub(r'All rights reserved.*$', '', text)
                            
                            if text.lower().startswith(word.lower() + ' '):
                                text = text[len(word):].strip()
                                
                            if len(text) > 20:
                                return text
                    
                    div_text = content_div.get_text(separator=' ', strip=True)
                    if div_text and len(div_text) > 50:
                        text = re.sub(r'\s+', ' ', div_text)[:500]  # Limit length
                        text = re.sub(r'BibleGateway\.com.*$', '', text)
                        if text.lower().startswith(word.lower() + ' '):
                            text = text[len(word):].strip()
                        return text
                        
            return None
            
        except Exception as e:
            print(f"Error fetching Easton's definition for '{word}': {e}")
            return None

    def fetch_wordnet_definitions(self, word: str) -> List[str]:
        try:
            synsets = wordnet.synsets(word.lower())
            definitions = []
            
            for synset in synsets:
                pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adjective', 
                          's': 'adjective satellite', 'r': 'adverb'}
                pos_full = pos_map.get(synset.pos(), synset.pos())
                definitions.append(f"{pos_full}: {synset.definition()}")
            
            return definitions
            
        except Exception as e:
            print(f"Error fetching WordNet definitions for '{word}': {e}")
            return []
    
    def fetch_definitions(self, word: str) -> Dict:
        print(f"Fetching definitions for: {word}")
        
        result = {
            "word": word,
            "definitions": {"wordnet": [], "easton": None}
        }
        
        print("    Fetching from WordNet...")
        wordnet_defs = self.fetch_wordnet_definitions(word)
        if wordnet_defs:
            result["definitions"]["wordnet"] = wordnet_defs
        else:
            print("    No definitions found in WordNet")

        print("    Fetching from Easton's Bible Dictionary...")
        easton_def = self.fetch_easton_definition(word)
        if easton_def:
            result["definitions"]["easton"] = easton_def
        else:
            print("    No definition found in Easton's Bible Dictionary")

        return result
    
    def save_to_json(self, data: Dict, filename: str):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Definitions saved to: {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")


def main():
    parser = argparse.ArgumentParser(description='Fetch word definitions from Easton\'s Bible Dictionary and WordNet')
    parser.add_argument('word', help='The word to look up definitions for')
    parser.add_argument('-o', '--output', default=None, 
                       help='Output JSON file (default: <word>_definitions.json)')
    
    args = parser.parse_args()
    fetcher = DefinitionFetcher()
    definitions = fetcher.fetch_definitions(args.word)
    
    output_file = args.output or f"{re.sub(r'[^\w\-_]', '_', args.word.lower())}_definitions.json"
    fetcher.save_to_json(definitions, output_file)
    
    total_defs = (1 if definitions["definitions"]["easton"] else 0) + len(definitions["definitions"]["wordnet"])
    
    print(f"\nSummary:")
    print(f"  Word: {args.word}")
    print(f"  Total definitions found: {total_defs}")
    print(f"  Easton's: {'Yes' if definitions['definitions']['easton'] else 'No'}")
    print(f"  WordNet: {len(definitions['definitions']['wordnet'])} definitions")
    print(f"  Output file: {output_file}")


if __name__ == "__main__":
    main()
