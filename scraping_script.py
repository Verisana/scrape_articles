import requests
import time

from collections import Counter
from lxml import html
from selenium import webdriver

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; U; Linux i686; '
                  'ru; rv:1.9.1.8) Gecko/20100214 '
                  'Linux Mint/8 (Helena) Firefox/'
                  '3.5.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
              '*/*;q=0.8',
    'Accept-Language': 'ru,en-us;q=0.7,en;q=0.3',
    'Accept-Encoding': 'deflate',
    'Accept-Charset': 'windows-1251,utf-8;q=0.7,*;q=0.7',
    'Keep-Alive': '300',
    'Connection': 'keep-alive',
    'Cookie': 'users_info[check_sh_bool]=none; '
              'search_last_date=2019-02-19; search_last_month=2019-02; '
              'PHPSESSID=b6df76a958983da150476d9cfa0aab18',
}

STRING_LENGTH_T = 20

TEXT_FINDER_XPATH = f'//body\
                    //*[not(\
                    self::script or \
                    self::noscript or \
                    self::style or \
                    self::i or \
                    self::em or \
                    self::b or \
                    self::strong or \
                    self::span or \
                    self::a)] \
                    /text()[string-length(normalize-space()) > ' \
                    f'{STRING_LENGTH_T}]/..'


def get_html_tree(url, use_selenium):
    """From some URL construct and return an HTML tree."""
    if not use_selenium:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            html_text = response.text
        else:
            raise Exception("Can't get response from passed URL")
    else:
        driver = webdriver.Firefox()
        driver.get(url)
        time.sleep(3)
        html_text = driver.page_source
        driver.close()
    return html.document_fromstring(html_text).getroottree()


def get_xpath_frequencydistribution(paths):
    """ Build and return a frequency distribution over xpath occurrences."""
    # "html/body/div/div/text" -> [ "html", "body", "div", "div", "text" ]
    splitpaths = [p.split('/') for p in paths]

    # get list of "parentpaths" by right-stripping off the last xpath-node,
    # effectively getting the parent path
    parentpaths = ['/'.join(p[:-1]) for p in splitpaths]

    # build frequency distribution
    parentpaths_counter = Counter(parentpaths)
    return parentpaths_counter.most_common()


def strip_path(path):
    return '/'.join(path.split('/')[:-1])


def get_xpath_sum_aver_length(hists, nodes):
    """Build and return array containing sum of average string lengths"""
    for hist in hists:
        new_item = [hist[0],
                    sum([node[1][2] if hist[0] == strip_path(node[0])
                         else 0 for node in nodes])]
        yield new_item


def calc_avgstrlen_pathstextnodes(pars_tnodes):
    """In the effort of not using external libraries (like scipy, numpy, etc),
    I've written some harmless code for basic statistical calculations
    """
    ttl = 0
    for _, tnodes in pars_tnodes:
        ttl += tnodes[3]  # index #3 holds the avg strlen

    crd = len(pars_tnodes)
    avg = ttl / crd
    return (avg, ttl, crd)


def calc_across_paths_textnodes(paths_nodes):
    """Given a list of parent paths tupled with children textnodes, plus
    initialized feature values, we calculate the total and average string
    length of the parent's children textnodes.
    """
    for paths_node in paths_nodes:
        cnt = len(paths_node[1][0])
        ttl = sum([len(s) for s in paths_node[1][0]])  # calculate total
        paths_node[1][1] = cnt  # cardinality
        paths_node[1][2] = ttl  # total
        paths_node[1][3] = ttl / cnt  # average


def get_parent_xpaths_and_textnodes(url, use_selenium,
                                    xpath_to_text=TEXT_FINDER_XPATH):
    """Provided a url, path or filelike obj., we construct an html tree,
    and build a list of parent paths and children textnodes & "feature"
    tuples.
    The features - descriptive values used for gathering statistics that
    attempts to describe this artificial environment I've created (parent
    paths and children textnodes) - are initialized to '0'
    Modifications of eatiht.get_sentence_xpath_tuples: some code was
    refactored-out, variable names are slightly different. This function
    does wrap the ltml.tree construction, so a file path, file-like
    structure, or URL is required.
    """
    html_tree = get_html_tree(url, use_selenium)

    xpath_finder = html_tree.getroot().getroottree().getpath

    nodes_with_text = html_tree.xpath(xpath_to_text)

    # read note 5
    parentpaths_textnodes = [
        (xpath_finder(n),
         [n.xpath('.//text()'),  # list of text from textnode
          0,  # number of texts (cardinality)
          0,  # total string length in list of texts
          0])  # average string length
        for n in nodes_with_text
    ]

    if len(parentpaths_textnodes) == 0:
        raise Exception("No text nodes satisfied the xpath:\n\n" +
                        xpath_to_text + "\n\nThis can be due to user's" +
                        " custom xpath, min_str_length value, or both")
    return parentpaths_textnodes


def get_optimal_hists_index(hists, sum_avers):
    for i, hist in enumerate(hists):
        for j, sum_aver in enumerate(sum_avers):
            if hist[0] == sum_aver[0] and i >= j:
                return i
            elif hist[0] == sum_aver[0]:
                break
    return 0


def extract(url, use_selenium=False):
    """A more precise algorithm over the original eatiht algorithm
    """
    pars_tnodes = get_parent_xpaths_and_textnodes(url, use_selenium)
    calc_across_paths_textnodes(pars_tnodes)

    avg, _, _ = calc_avgstrlen_pathstextnodes(pars_tnodes)

    filtered = [parpath_tnodes for parpath_tnodes in pars_tnodes
                if parpath_tnodes[1][2] > avg]

    paths = [path for path, tnode in filtered]

    hists = get_xpath_frequencydistribution(paths)
    sum_avers = list(get_xpath_sum_aver_length(hists, filtered))
    sum_avers.sort(key=lambda x: x[1], reverse=True)
    hist_index = get_optimal_hists_index(hists, sum_avers)
    try:
        target_tnodes = [tnode for par, tnode in pars_tnodes if
                         hists[hist_index][0] in par]

        target_text = '\n\n'.join(
            [' '.join(tnode[0]) for tnode in target_tnodes])

        return target_text
    except IndexError:
        return ""


def usage_example():
    urls = [
        "https://meduza.io/feature/2020/02/11/para-iz-kaliningrada-priglasila-na-svadbu-sotrudnika-fsb-teper-suprugov-obvinyayut-v-gosizmene-iz-za-fotografiy-s-prazdnika",
        "https://www.gazeta.ru/army/news/2020/02/11/14022127.shtml",
        "https://lenta.ru/news/2020/02/11/mashtab/",
        "https://www.gazeta.ru/business/2020/02/10/12952741.shtml",
    ]
    extracted_texts = [extract(url, False) for url in urls]
    for text in extracted_texts:
        print('*' * 50 + '\n' + text)


usage_example()
