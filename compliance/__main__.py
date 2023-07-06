#!/usr/bin/env python
import argparse, jieba, json, logging, openai, os, re, sys, warnings

from gensim import corpora, models, similarities
from pathlib import Path
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings(action='ignore', category=CryptographyDeprecationWarning)

global level

module = sys.modules['__main__'].__file__
log = logging.getLogger(module)

def __load_snippets__(file):
    with open(file) as json_file:
        return json.load(json_file)

def __find_similar__(dictionary, corpus, tfidf, feature_cnt, snippets, text):
    kw_vector = dictionary.doc2bow(jieba.lcut(text))
    index = similarities.SparseMatrixSimilarity(
        tfidf[corpus], num_features=feature_cnt
    )
    sim = list(index[tfidf[kw_vector]])
    index = sim.index(max(sim))
    return snippets[list(snippets)[index]]

snippets_dir = os.path.join(os.path.dirname(__file__), 'snippets')

predetermined = [
  {"type" : "terraform-compliance", "format": "gherkin", "snippets": "terraform-compliance.json", "extention": ".feature"},
  {"type" : "Azure Policy", "format": "json", "snippets": "azure.json", "extention": ".json"}
]

def generate(args):

    print("\nRules asked:\n %s" % (args.prompt), "\n");

    try:
        for item in predetermined:
        
            # Loadsnippets and create a vector corpus
            snippets = __load_snippets__(os.path.join(os.path.dirname(__file__),"%s/%s" % (snippets_dir, item.get("snippets"))))
            analyzed_snippets = [ jieba.lcut(snippet.lower()) for snippet in snippets ]
            dictionary = corpora.Dictionary(analyzed_snippets)
            corpus = [ dictionary.doc2bow(snippet) for snippet in analyzed_snippets ]
            tfidf = models.TfidfModel(corpus)
            feature_cnt = len(dictionary.token2id)
            
            # Vector similarity search to snippets template
            snippet = __find_similar__(dictionary, corpus, tfidf, feature_cnt, snippets, args.prompt)
            
            log.debug(snippet)
            
            # Request to OpenAI
            openai.api_key = os.getenv("OPENAI_API_KEY")
            system_message = (
              "You are an %s expert. No comment. %s:" % (item.get("type"), item.get("format"))
            )
            system_user = (
                    "You must generate %s code for provider Azure, the following policies: %s, using the options from the provided template %s, No comments, %s output:" % (item.get("type"), args.prompt.capitalize(), item.get("snippets"), item.get("format"))
            )
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0301",
                messages=[
                    {
                        "role": "system",
                        "content": system_message,
                    },
                    {"role": "user", "content": system_user},
                ],
                temperature=args.temperature,
            )
            result = response["choices"][0]["message"]["content"];
        
            log.debug(result)
        
            # Search result in output
            m = re.search(r'```(.|\n)*?```', result);
            if m:
              result = m.group(0)
            else:
              result = "```%s\n%s\n```" % (item.get("format"), result)
        
            # Show result
            print("\n✓ Generated %s rules for Azure:\n" % (item.get("type")), "\n", result, "\n");
            
            # Write files
            f = open("%s%s" % (args.feature, item.get("extention")), "w")
            f.write(result.replace('```json', '').replace('```', ''))
            f.close()
    
    except Exception as e:
       log.error('{c} - {m}'.format(c = type(e).__name__, m = str(e)))
       sys.exit(os.EX_SOFTWARE)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--feature", type=str, dest='feature', required=True,
                        help="Name for your feature rule group")
    parser.add_argument("-p", "--prompt", type=str, dest='prompt', required=True,
                        help="Natural language rules that need to be translated into Azure Policy and Terraform-compliance")
    parser.add_argument("-t", "--temperature", type=float, dest='temperature', required=False, default=0,
                        help="Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Increase output verbosity")
    args = parser.parse_args()

    if args.verbose:
        level=logging.DEBUG
    else:
        level=logging.ERROR

    # Set logging config   
    logging.basicConfig(stream=sys.stderr, level=level, format='(%(levelname)s): %(message)s')

    # Generate code to Azure Policy and Terraform-compliance
    generate(args)
