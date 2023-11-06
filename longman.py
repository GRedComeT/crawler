import requests
from bs4 import BeautifulSoup
from munch import Munch
import re
import json
import argparse


def scrape_longman(word, port=1080):
    """_summary_

    Args:
        word (_type_): _description_
    """
    url = f"https://www.ldoceonline.com/dictionary/{word}"
    
    header = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Connection':'close'
    }
    proxy = f'http://127.0.0.1:{port}'
    response = requests.get(url, headers=header, proxies={'https': proxy})
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Extract data
        data = extract_data(soup)
        data = process_data(data)
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
            entry.gram = gram.text.strip()
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
      + **{SIGNPOST}** [gram if not global.gram] {define} | [SYN|OPP]:{syn|opp}
        + {example} -> if not collo
        
        + **{collo}** -> if collo
          + {example}
        + **{GramExa}**
          + {example} -> if gramexa
    ```
    
    Args:
        data (list[Munch()]): list of Munch() which are json style
    """
    headTemplate = '+ {word} ({hyphenation}, {proncode}{pos}. {tooltiplevel}{freq}[Amp]({speechurl})) {gram}\n'
    defTemplate = '  + {signpost}{gram}{define}{SYN}{OPP}\n'
    
    
    results = []
    
    for dictEntry in data:
        ''' Every entries have a head and a list of senses, which contains one define and a list of examples'''

        entries = []
        head_dict = resolve_Head(dictEntry)
        headString = headTemplate.format(**head_dict)
        entries.append(headString)
        senses = dictEntry.sense
        # sense are list[Munch()]
        for sense in senses:
            def_dict = resolve_Def(sense)
            defString = defTemplate.format(**def_dict)
            entries.append(defString)
            examples = sense.examples
            exampleString = ""
            for example in examples:
                if isinstance(example, str):
                    exampleString += '    + ' + example + '\n'
                elif isinstance(example, Munch):
                    if 'COLLO' in example:
                        exampleString += '    + **' + example.COLLO + '**\n'
                        for in_example in example.examples:
                            exampleString += '      + ' + in_example + '\n'
                    elif 'PROP' in example:
                        exampleString += '    + **' + example.PROP + '**\n'
                        for in_example in example.examples:
                            exampleString += '      + ' + in_example + '\n'
                    else:
                        raise Exception('Unknown example type')
                else:
                    raise Exception('Unknown example type')
            entries.append(exampleString)
        results.append(''.join(entries))
    return results
        
    
    

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
        filling_dict.gram = filling_dict.gram
    return filling_dict
      
def resolve_Def(sense) -> Munch():
    def_dic = Munch()
    def_dic.signpost = sense.get('signpost', "")
    if def_dic.signpost != "":
        def_dic.signpost = '**' + def_dic.signpost + '** '
    def_dic.gram = sense.get('gram', "")
    if def_dic.gram != "":
        def_dic.gram = def_dic.gram + ' '
    def_dic.define = sense.define
    def_dic.SYN = sense.get('syn', "")
    if def_dic.SYN != "":
        def_dic.SYN = ' | SYN: ' + ', '.join(def_dic.SYN)
    def_dic.OPP = sense.get('opp', "")
    if def_dic.OPP != "":
        def_dic.OPP = ' | OPP: ' + ', '.join(def_dic.OPP)
    return def_dic

def store_data(data):
    """_summary_

    Args:
        data (_type_): _description_
    """
    with open('words.md', 'a+', encoding='utf-8') as f:
        f.write('\n'.join(data))
        # json.dump(data, f, ensure_ascii=False, indent=4)
        


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--word', type=str, default="", help='Word to search')
    parser.add_argument('--port', type=int, default=1080, help='Proxy port')
    parser = parser.parse_args()
    word = parser.word
    if word != "":
        scrape_longman(word, port=parser.port)
    else:
        test_word = ['drink', 'mimic', 'malicious', 'narrow', 'deficiency', 'evident']
        for word in test_word:
            scrape_longman(word, port=parser.port)