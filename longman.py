import requests
from bs4 import BeautifulSoup
from munch import Munch
import re
import json
import argparse


def scrape_longman(word):
    """_summary_

    Args:
        word (_type_): _description_
    """
    url = f"https://www.ldoceonline.com/dictionary/{word}"
    
    header = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Connection':'close'
    }
    
    response = requests.get(url, headers=header, proxies={'https': 'http://127.0.0.1:1080'})
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Extract data
        data = extract_data(soup)
        process_data(data)
        # Store data
        store_data(data)
    else:
        print("Error: ", response.status_code)
    response.close()
        
        
def extract_data(soup):
    """Extract data from soup
    TODO: Add more html tree framework to extract more data
    
    Return a list of Munch() which are json style
    
    Args:
        soup (bs4.soup): parsed html
    """
    all_dictentries = soup.find_all('span', attrs={'class': 'dictentry'})
    filtered_dictentries = []
    # Only remain the Longman Dictionary of Contemporary English
    for dicts in all_dictentries:
        if dicts.find('span', class_='bussdictEntry') == None:
            filtered_dictentries.append(dicts)
    all_entry = []
    
    for dicts in filtered_dictentries:
        # Resolved Entry
        entry = Munch()
        
        # Get Frequent Head
        frequent_head = dicts.find('span', class_='Head')
        # Get Word
        try:
            word = frequent_head.find('span', attrs={'class': 'HWD'}).text
            entry.word = word
        except:
            print(dicts)
        
        # Get Hyphenation
        if (hyphenation := frequent_head.find('span', attrs={'class': 'HYPHENATION'})) != None:
            entry.hyphenation = hyphenation.text.strip()
        # hyphenation = frequent_head.find('span', attrs={'class': 'HYPHENATION'}).text.strip()
        # entry.hyphenation = hyphenation
        # Get Pronunciation
        proncode = frequent_head.find('span', attrs={'class': 'PRON'})
        if proncode != None:
            entry.proncode = proncode.text.strip()
        # Get Tooltiplevel
        tooltiplevel = frequent_head.find('span', attrs={'class': 'tooltip LEVEL'})
        if tooltiplevel != None:
            entry.tooltiplevel = tooltiplevel.get('title')
            entry.tooltiplevel = entry.tooltiplevel.lstrip('Core vocabulary: ')
        if len(freqs := frequent_head.find_all('span', attrs={'class': 'FREQ'})) != 0:
            entry.freq = []
            for freq in freqs:
                entry.freq.append(freq.text.strip())
        # Get Pos
        entry.pos = frequent_head.find('span', attrs={'class': 'POS'}).text.strip()
        # Get Speech
        entry.speechurl = frequent_head.find('span', attrs={'title': f'Play American pronunciation of {entry.word}'}).get('data-src-mp3')
        # Get Global GRAM
        gram = frequent_head.find('span', attrs={'class': 'GRAM'})
        is_gram = False
        if gram != None:
            entry.gram = '[' + gram.text.strip() + ']'
            is_gram = True 
        # Get Sense
        senses = dicts.find_all('span', attrs={'class': 'Sense'})
        entry.sense = []
        for sense in senses:
            # Drop out the sense which can not have DEF
            if sense.find('span', attrs={'class': 'DEF'}) == None:
                continue
            # Resolved Sense
            singleSense = Munch()
            # Get Gram if have not 'global gram'
            if is_gram == False and (gram := sense.find('span', attrs={'class': 'GRAM'})) != None:
                singleSense.gram = gram.text
            # Get SIGNPOST
            if (signpost := sense.find('span', attrs={'class': 'SIGNPOST'})) != None:
                singleSense.signpost = signpost.text
            # Get DEF
            singleSense.define = sense.find('span', attrs={'class': 'DEF'}).text
            # Get SYN or OPP
            if len(syns := sense.find_all('span', attrs={'class': 'SYN'})) != 0:
                singleSense.syn = []
                for syn in syns:
                    singleSense.syn.append(syn.text.lstrip('SYN ').strip(',').strip())
            if len(opps := sense.find_all('span', attrs={'class': 'OPP'})) != 0:
                singleSense.opp = []
                for opp in opps:
                    singleSense.opp.append(opp.find('span', class_='span').next_sibling.text.strip())
                    
            # Get Examples
            singleSense.examples = []
            examples = sense.select('span.EXAMPLE, span.ColloExa, span.GramExa')
            for example in examples:
                if example.get('class')[0] == 'EXAMPLE':
                    singleSense.examples.append(example.text.strip())
                elif example.get('class')[0] == 'ColloExa':
                    temp = Munch()
                    temp.COLLO = example.find('span', attrs={'class': 'COLLO'}).text.strip()
                    temp.examples = []
                    in_examples = example.find_all('span', attrs={'class': 'EXAMPLE'})
                    for in_example in in_examples:
                        temp.examples.append(in_example.text.strip())
                    singleSense.examples.append(temp)
                elif example.get('class')[0] == 'GramExa':
                    temp = Munch()
                    temp.PROP = example.find('span', class_=re.compile(r'PROP\w+')).text.strip()
                    temp.examples = []
                    in_examples = example.find_all('span', attrs={'class': 'EXAMPLE'})
                    for in_example in in_examples:
                        temp.examples.append(in_example.text.strip())
                    singleSense.examples.append(temp)
                else:
                    raise Exception('Unknown example type')
            
            entry.sense.append(singleSense)
            
        all_entry.append(entry)
        
    
    return all_entry
    
def debug(data):
    print(type(data))
    print()
    print(data)
    
def process_data(data):
    """Transform data to markdown format by My obsidian template
    
    ```
    + {word}({hypenation} {proncode} {pos} {tooltiplevel} {freq} {[speechurl]}) [gram] -> if global.gram
      + **{SIGNPOST}** [gram if not global.gram] {define} | [SYN|OPP]:{syn|opp} -> {RelatedWD}
        + {example} -> if not collo
        
        + **{collo}** -> if collo
          + {example}
        + **{GramExa}**
          + {example} -> if gramexa
    ```
    
    Args:
        data (list[Munch()]): list of Munch() which are json style
    """
    headTemplate = '{word} ({hyphenation}, {proncode}{pos}, {tooltiplevel}{freq}[{speechurl}]) {gram}'
    
    for dictEntry in data:
        filling_dict = resolve_Head(dictEntry)
        headString = headTemplate.format(**filling_dict)
        print(headString)
        senses = dictEntry.sense
        # sense are list[Munch()]
        for sense in senses:
            pass
        
    
    

def resolve_Head(dictEntry) -> Munch():
    filling_dict = Munch()
    filling_dict.word = dictEntry.word
    filling_dict.hyphenation = dictEntry.hyphenation
    filling_dict.proncode = dictEntry.get('proncode', "")
    if filling_dict.proncode != "":
        filling_dict.proncode = '/' + filling_dict.proncode + '/, '
    filling_dict.pos = dictEntry.pos
    filling_dict.tooltiplevel = dictEntry.get('tooltiplevel', "")
    if filling_dict.tooltiplevel != "":
        filling_dict.tooltiplevel += ', '
    filling_dict.freq = dictEntry.get('freq', "")
    if filling_dict.freq != "":
        if len(filling_dict.freq) == 1:
            filling_dict.freq = filling_dict.freq[0]
        else:
            filling_dict.freq = filling_dict.freq[0] + ', ' + filling_dict.freq[1]
        filling_dict.freq += ', '
    filling_dict.speechurl = dictEntry.speechurl
    filling_dict.gram = dictEntry.get('gram', "")
    if filling_dict.gram != "":
        filling_dict.gram = '[' + filling_dict.gram + ']'
    return filling_dict
      
    

def store_data(data):
    """_summary_

    Args:
        data (_type_): _description_
    """
    with open('words.md', 'w', encoding='utf-8') as f:
        # f.write(data)
        json.dump(data, f, ensure_ascii=False, indent=4)
        


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--word', type=str, required=True, help='Word to search')
    parser = parser.parse_args()
    word = parser.word
    test_word = ['drink', 'mimic', 'malicious', 'narrow', 'deficiency', 'evident']
    for word in test_word:
        scrape_longman(word)