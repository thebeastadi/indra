import urllib, urllib2
import xml.etree.ElementTree as ET

pubmed_search = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
pubmed_fetch = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'

def send_request(url, data):
    try:
        req = urllib2.Request(url, data)
        res = urllib2.urlopen(req)
        xml_str = res.read()
        tree = ET.fromstring(xml_str)
    except:
        return None
    return tree

def get_ids(search_term, retmax=1000):
    params = {'db': 'pubmed',
                'term': search_term,
                'retstart': 0,
                'retmax': retmax}
    tree = send_request(pubmed_search, urllib.urlencode(params))
    if tree is None:
        return []
    count = int(tree.find('Count').text)
    id_terms = tree.findall('IdList/Id')
    if id_terms is None:
        return []
    ids = [idt.text for idt in id_terms]
    if count != len(ids):
        print 'Not all ids were retreived, limited at %d.' % retmax
    return ids

def get_abstract(pubmed_id):
    params = {'db': 'pubmed',
                'retmode': 'xml',
                'rettype': 'abstract',
                'id': pubmed_id}
    tree = send_request(pubmed_fetch, urllib.urlencode(params))
    if tree is None:
        return None
    article = tree.find('PubmedArticle/MedlineCitation/Article')
    if article is None:
        return None
    abstract = article.findall('Abstract/AbstractText')
    if abstract is None:
        return None
    else:
        abstract_text = ' '.join([' ' if abst.text is None 
                                    else abst.text for abst in abstract])
        return abstract_text