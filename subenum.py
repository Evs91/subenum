banner = """
 _______ _     _ ______  _______ __   _ _     _ _______
 |______ |     | |_____] |______ | \  | |     | |  |  |
 ______| |_____| |_____] |______ |  \_| |_____| |  |  |
                                   by zen
"""

try:
    from requests import Session
    from requests.auth import HTTPBasicAuth
    from bs4 import BeautifulSoup
    from fake_useragent import UserAgent
    from urllib.parse import unquote
    from argparse import ArgumentParser
    from os import getenv
    from dotenv import load_dotenv
    from threading import Thread
    from time import time, sleep
except KeyboardInterrupt:
    print(banner)
    print("[*] Exiting...")


# main CLI function
def main():

    # print the banner
    print(banner)

    # parse the cli parameters
    parser = ArgumentParser(description="Subdomains Enumerator")
    parser.add_argument('domain', type=str, help="Domain to search for subdomains")
    parser.add_argument('-o', '--output', type=str, help="Save the output in a text file")
    parser.add_argument('-f', '--fast', action='store_true', help="Enable fast mode")
    parser.add_argument('-q', '--quiet', action='store_true', help="Disable verbosity")
    args = parser.parse_args()

    # load the api keys
    load_dotenv()
    vt_api_key = getenv('VIRUSTOTAL_API_KEY')
    shodan_api_key = getenv('SHODAN_API_KEY')
    censys_appid = getenv('CENSYS_APP_ID')
    censys_secret = getenv('CENSYS_SECRET')

    # get the subdomains from subenum
    verbose = True if args.quiet == False else False
    subenum = SubEnum(
        verbose=verbose,
        vt_api_key=vt_api_key,
        shodan_api_key=shodan_api_key,
        censys_appid=censys_appid,
        censys_secret=censys_secret,
        fast=args.fast
    )
    subdomains = subenum.get_subdomains(args.domain)

    # print the subdomains is there is no output
    if args.output is None:
        for subdomain in subdomains:
            print(subdomain)
    
    # dump the subdomains list to the output file
    else:
        with open(args.output, 'w') as output_file:
            for subdomain in subdomains:
                output_file.write(subdomain + '\n')


# SubEnum controller
class SubEnum():

    # create a subenum object
    def __init__(self, verbose=True, vt_api_key=None, shodan_api_key=None, censys_appid=None, censys_secret=None, fast=False):
        self.verbose = verbose

        # load all the modules
        self.modules = []
        self.modules.append(ThreatCrowd(verbose=verbose))
        self.modules.append(CertificatesSearch(verbose=verbose))
        self.modules.append(DNSDumpster(verbose=verbose))
        self.modules.append(Google(verbose=verbose, fast=fast))
        self.modules.append(Bing(verbose=verbose, fast=fast))
        self.modules.append(Yahoo(verbose=verbose, fast=fast))

        # load all the modules that needs api keys
        if vt_api_key is not None:
            self.modules.append(VirusTotal(vt_api_key, verbose=verbose, fast=fast))
        if shodan_api_key is not None:
            self.modules.append(Shodan(shodan_api_key, verbose=verbose))
        if censys_appid is not None and censys_secret is not None:
            self.modules.append(Censys(censys_appid, censys_secret, verbose=verbose))

    # get a list of subdomains
    def get_subdomains(self, domain):

        # get the subdomains from all the modules
        start_time = time()
        subdomains = self.run_modules_scan(domain)
        elapsed_time = "%0.2f" % (time() - start_time)

        # sort all the subdomains
        subdomains = self.sort_subdomains(subdomains)

        # print the number of subdomains found
        if self.verbose == True:
            print(f"[*] Found a total of {len(subdomains)} subdomains in {elapsed_time} secs.")

        # return all the subdomains
        return subdomains
    
    # run all the modules to scan for subdomains
    def run_modules_scan(self, domain):

        # create a list of all the subdomains found
        subdomains = []

        # start a thread for each modules
        threads = []
        for module in self.modules:
            thread = Thread(target=module.get_subdomains, args=(domain,))
            threads.append(thread)
            thread.start()

        # wait for all the threads to finish
        for thread in threads:
            thread.join()

        # merge all the subdomains list
        subdomains = []
        for module in self.modules:
            if module.subdomains is not None:
                for subdomain in module.subdomains:
                    if subdomain not in subdomains:
                        subdomains.append(subdomain)

        # return the subdomains found
        return subdomains

    # sort a list of subdomains
    def sort_subdomains(self, subdomains):
        valid_subdomains = []
        for subdomain in subdomains:
            if all((char.isalnum() or char in ['-', '.']) for char in subdomain) == True:
                valid_subdomains.append(subdomain)
                continue
        return sorted(valid_subdomains)


# default module api class
class ModuleApi:

    # create an api object
    def __init__(self, verbose=True, fast=False):
        self.base_name = self.__class__.__name__
        self.session = Session()
        self.verbose = verbose
        self.subdomains = None
        self.fast_scan = fast

    # get the subdomains from the api
    def get_subdomains(self, domain):

        # query the subdomains
        if self.verbose == True:
            self.print("Starting subdomains discovery...")
        response = self.query_domain(domain)
        if response is None:
            return None

        # parse the subdomains from the response
        self.subdomains = self.parse_query_response(response, domain)
        if self.subdomains is None:
            return None
        
        # return the subdomains
        if self.verbose == True:
            subdomains_count = len(self.subdomains)
            self.print(f"{subdomains_count if subdomains_count > 0 else 'no'} subdomain{'s' if subdomains_count != 1 else ''} found.")
        return self.subdomains
    
    # query the domain
    def query_domain(self, domain):
        return None
    
    # parse the query response
    def parse_query_response(self, text, domain):
        return None
    
    # get a domain from an url
    def get_domain_from_url(self, url):

        # remove the protocol
        if url.startswith('http://') == True:
            url = url[7:]
        elif url.startswith('https://') == True:
            url = url[8:]
        else:
            return None
        
        # remove the path
        pos = url.find('/')
        if pos != -1:
            url = url[:pos]

        # remove the parameters
        pos = url.find('?')
        if pos != -1:
            url = url[:pos]

        # remove the port
        pos = url.find(':')
        if pos != -1:
            url = url[:pos]

        # return the url domain
        return url
    
    # print a message from the module
    def print(self, text):
        print(f"[*] \033[92m{self.base_name}\033[0m: {text}")

    # print an error message from the module
    def print_error(self, text):
        self.print(f"\033[91merror\033[0m: {text}")
    

# default module search engine class
class ModuleSearchEngine(ModuleApi):

    # get the subdomains from the search engine
    def get_subdomains(self, domain):

        # query the first 10 pages
        if self.verbose == True:
            self.print("Starting subdomains discovery...")
        self.subdomains = []
        for page in range(1, 10):

            # query the current page
            response = self.query_domain_page(domain, page)
            if response is None:
                break

            # parse the subdomains from the page response
            page_subdomains = self.parse_query_response(response, domain)
            if page_subdomains is None:
                break

            # add the subdomains found to the list
            for subdomain in page_subdomains:
                if subdomain not in self.subdomains:
                    self.subdomains.append(subdomain)

            # stop at the first page if we are in fast mode
            if self.fast_scan == True:
                break

        # return the complete list of all subdomains found
        if self.verbose == True:
            subdomains_count = len(self.subdomains)
            self.print(f"{subdomains_count if subdomains_count > 0 else 'no'} subdomain{'s' if subdomains_count != 1 else ''} found.")
        return self.subdomains
    
    # query a domain page
    def query_domain_page(self, domain, page):
        return None
    

# default module api class with a key
class ModuleApiWithKey(ModuleApi):

    # create an api object
    def __init__(self, api_key, verbose=True, fast=False):
        super().__init__(verbose=verbose, fast=fast)
        self.api_key = api_key


# default module api class with an auth
class ModuleApiWithAuth(ModuleApi):

    # create an api object
    def __init__(self, username, password, verbose=True, fast=False):
        super().__init__(verbose=verbose, fast=fast)
        self.auth = HTTPBasicAuth(username, password)


# ThreatCrowd api
class ThreatCrowd(ModuleApi):

    # create a ThreatCrowd object
    def __init__(self, verbose=True):
        super().__init__(verbose=verbose)
        self.base_url = "http://ci-www.threatcrowd.org/graphHtml.php"

    # download a domain report
    def query_domain(self, domain):

        # query the website
        params = { 'domain': domain }
        response = self.session.get(self.base_url, params=params)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the text response
        return response.text
    
    # parse a domain report
    def parse_query_response(self, text, domain):

        # find where the subdomains are
        pos = text.find("elements: {")
        end_pos = text.find("edges: [")
        text = text[pos:end_pos]
        lines = text.split('\n')

        # parse all subdomains
        subdomains = []
        for line in lines:
            pos = line.find("id: '")
            if pos != -1:
                id = line[pos + 5:]
                end_pos = id.find("'")
                id = id[:end_pos]
                if id.endswith(domain) == True:
                    while id[0] == '.':
                        id = id[1:]
                    if id == domain:
                        continue
                    if id in subdomains:
                        continue
                    subdomains.append(id)

        # return the list of subdomains
        return subdomains


# crt.sh api
class CertificatesSearch(ModuleApi):

    # create a crtsh object
    def __init__(self, verbose=True):
        super().__init__(verbose=verbose)
        self.base_url = "https://crt.sh/"
    
    # query a domain informations from crt.sh
    def query_domain(self, domain, try_count=0):

        # query the website
        params = { 'q': domain }
        response = self.session.get(self.base_url, params=params)

        # check for errors
        if response.status_code in [502, 503]:
            if try_count < 3:
                return self.query_domain(domain, try_count=try_count + 1)
            if self.verbose == True:
                self.print_error(f"service is currently unavailable.")
            return None
        elif response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the text response
        return response.text
    
    # parse a query response from crt.sh
    def parse_query_response(self, text, domain):

        # convert the text response to html
        soup = BeautifulSoup(text, features="html.parser")

        # parse the subdomains from the html
        subdomains = []
        outers = soup.find_all('td', {'class': 'outer'})
        for outer in outers:
            elems_list = outer.find_all("tr")
            for elem in elems_list:
                fields_list = elem.find_all('td')
                if len(fields_list) == 7:
                    field_id = 0
                    for field in fields_list:
                        if field_id in [4, 5]:
                            lines = str(field).split('<br/>')
                            for subdomain in lines:
                                if subdomain.startswith('<td>') == True:
                                    subdomain = subdomain[4:]
                                if subdomain.endswith('</td>') == True:
                                    subdomain = subdomain[:-5]
                                if subdomain.endswith(domain) == False:
                                    continue
                                if subdomain not in subdomains:
                                    subdomains.append(subdomain)
                        field_id += 1
        
        # return the subdomains found
        return subdomains


# DNSDumpster api
class DNSDumpster(ModuleApi):

    # create a dnsdumpster object
    def __init__(self, verbose=True):
        super().__init__(verbose=verbose)
        self.base_url = "https://dnsdumpster.com/"

    # get the subdomains from dnsdumpster
    def get_subdomains(self, domain):

        # query the csrf token
        if self.verbose == True:
            self.print("Starting subdomains discovery...")
        response = self.query_csrf_token()
        if response is None:
            return None

        # parse the csrf token from the response
        csrf_token = self.parse_csrf_token_response(response)
        if csrf_token is None:
            return None

        # query the domain from dnsdumpster
        response = self.query_domain(domain, csrf_token)
        if response is None:
            return None

        # parse the subdomains from the response
        self.subdomains = self.parse_query_response(response, domain)
        if self.subdomains is None:
            return None
        
        # return the subdomains
        if self.verbose == True:
            subdomains_count = len(self.subdomains)
            self.print(f"{subdomains_count if subdomains_count > 0 else 'no'} subdomain{'s' if subdomains_count != 1 else ''} found.")
        return self.subdomains
    
    # query a csrf token from dnsdumpster
    def query_csrf_token(self):

        # query the website
        response = self.session.get(self.base_url)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code '{response.status_code}' while trying to get csrf token.")
            return None
        
        # return the response text
        return response.text
    
    # parse a query response
    def parse_csrf_token_response(self, text):
        soup = BeautifulSoup(text, features="html.parser")
        input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        return input["value"]
    
    # query a domain informations from dnsdumpster
    def query_domain(self, domain, csrf_token):

        # query the website
        cookies = { 'csrftoken': self.session.cookies["csrftoken"] }
        headers = { 'referer': 'https://dnsdumpster.com/' }
        data = { 'csrfmiddlewaretoken': csrf_token, 'targetip': domain, 'user': 'free' }
        response = self.session.post(self.base_url, cookies=cookies, headers=headers, data=data)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the response text
        return response.text
    
    # parse a query response from dnsdumpster
    def parse_query_response(self, text, domain):
        
        # convert the text response to html
        soup = BeautifulSoup(text, features="html.parser")
        tables = soup.find_all('table', {'class': 'table'})

        # parse the subdomains from the tables
        subdomains = []
        for table in tables:
            td_list = table.find_all('td', {'class': 'col-md-4'})
            for td in td_list:
                for elem in td:
                    subdomain = str(elem)
                    pos = subdomain.find(' ')
                    if pos != -1:
                        subdomain = subdomain[pos + 1:]
                    if subdomain.endswith(domain) == True:
                        if subdomain not in subdomains:
                            subdomains.append(subdomain)
                    break

        # return the subdomains found
        return subdomains


# Google api
class Google(ModuleSearchEngine):

    # create a google object
    def __init__(self, verbose=True, fast=False):
        super().__init__(verbose=verbose, fast=fast)
        self.base_url = "https://www.google.com/search"

    # query a domain page from google
    def query_domain_page(self, domain, page):

        # query the website
        headers = { 'user-agent': UserAgent().random }
        params = { 'q': domain, 'start': (page - 1) * 10 }
        response = self.session.get(self.base_url, headers=headers, params=params)

        # check for errors
        if response.status_code == 429:
            if self.verbose == True:
                self.print_error(f"too many requests.")
            return None
        elif response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the response text
        return response.text
    
    # parse the query response from google
    def parse_query_response(self, text, domain):

        # convert the text response to html
        soup = BeautifulSoup(text, features="html.parser")
        if soup.find('title').text.find(domain) == -1:
            if self.verbose == True:
                self.print_error("captcha detected.")
            return None
        
        # find the links from the html
        rso = soup.find('div', {'id': 'rso'})
        urls = []
        total_urls = 0
        if rso is not None:
            for tag in rso:
                a_tags = tag.find_all('a')
                for a_tag in a_tags:
                    total_urls += 1
                    try:
                        if a_tag['href'] not in urls:
                            urls.append(a_tag['href'])
                    except KeyError:
                        pass
        
        # check if we are shadow banned
        if total_urls == 0:
            if self.verbose == True:
                self.print_error("shadow ban detected.")
                pass
            return None
        
        # parse a subdomains list from the urls list
        subdomains = []
        for url in urls:
            subdomain = self.get_domain_from_url(url)
            if subdomain is not None and subdomain.endswith(domain) == True:
                if subdomain not in subdomains:
                    subdomains.append(subdomain)

        # return the subdomains list
        return subdomains


# Bing api
class Bing(ModuleSearchEngine):

    # create a bing object
    def __init__(self, verbose=True, fast=False):
        super().__init__(verbose=verbose, fast=fast)
        self.base_url = "https://www.bing.com/search"
        self.user_agent = UserAgent().random

    # query the domain from bing
    def query_domain_page(self, domain, page):
        
        # query the website
        headers = { 'user-agent': self.user_agent }
        first = '1' if page == 1 else f"{(page - 1)}1"
        params = { 'q': domain, 'first': first }
        response = self.session.get(self.base_url, headers=headers, params=params)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the response text
        return response.text
    
    # parse a query response from bing
    def parse_query_response(self, text, domain):

        # convert the text response to html
        try:
            soup = BeautifulSoup(text, features="html.parser")
        except TypeError:
            if self.verbose == True:
                self.print_error("received unknown content type.")
            return None
        
        # check if we got a captcha
        title = soup.find('title').text
        if title.find(domain) == -1:
            if self.verbose == True:
                self.print_error("captcha detected.")
            return None
        
        # parse the results from the html
        b_results = soup.find('ol', {'id': 'b_results'})
        results = b_results.find_all('li', {'class': 'b_algo'})

        # parse all subdomains from the results
        subdomains = []
        results_domains = []
        for result in results:
            link = result.find('a', {'class': 'tilk'})
            if link is None:
                if self.verbose == True:
                    self.print_error("shadow ban detected.")
                return None
            link = link['href']
            if link.startswith('https://') == True:
                result_domain = link[8:]
            elif link.startswith('http://') == True:
                result_domain = link[7:]
            pos = result_domain.find('/')
            if pos != -1:
                result_domain = result_domain[:pos]
            if result_domain not in results_domains:
                results_domains.append(result_domain)
            if result_domain.endswith(domain) == True:
                subdomains.append(result_domain)
        
        # check if we got a shadow ban
        if results_domains == [ 'www.bing.com' ]:
            if self.verbose == True:
                self.print_error("shadow ban detected.")
            return None
        
        # return the list of subdomains
        return subdomains


# Yahoo api
class Yahoo(ModuleSearchEngine):

    # create a yahoo object
    def __init__(self, verbose=True, fast=False):
        super().__init__(verbose=verbose, fast=fast)
        self.base_url = "https://fr.search.yahoo.com/search"
        self.user_agent = UserAgent().random

    # query the domain from yahoo
    def query_domain_page(self, domain, page):
        
        # query the website
        headers = { 'user-agent': self.user_agent }
        params = {
            'p': domain,
            'ei': 'UTF-8',
            'nocache': 1,
            'nojs': 1
        }
        if page > 1:
            page_offset = ((page - 1) * 7) + 1
            params['b']  = page_offset
        response = self.session.get(self.base_url, headers=headers, params=params)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the response
        return response
    
    # parse a query response from yahoo
    def parse_query_response(self, response, domain):

        # parse the html text
        text = response.text
        try:
            soup = BeautifulSoup(text, features="html.parser")
        except TypeError:
            if self.verbose == True:
                self.print_error("received unknown content type.")
            return None
        
        # find all links
        links = soup.find_all('a')
        subdomains = []
        for link in links:

            # parse the link url
            try:
                url = link['href']
            except KeyError:
                continue

            # check if the url is 'yahoo encoded'
            if url.startswith("https://r.search.yahoo.com") == True:
                tokens = url.split('/')[3:]
                for token in tokens:
                    keyval = token.split('=')
                    if keyval[0] == 'RU':
                        url = unquote(keyval[1])
                        break

            # get the subdomain from the url
            subdomain = self.get_domain_from_url(url)
            if subdomain is not None and subdomain.endswith(domain) == True:
                if subdomain not in subdomains:
                    subdomains.append(subdomain)
        
        # return the list of subdomains found
        return subdomains


# VirusTotal api
class VirusTotal(ModuleApiWithKey):

    # create a VirusTotal object
    def __init__(self, api_key, verbose=True, fast=False):
        super().__init__(api_key, verbose=verbose, fast=fast)
        self.base_url = "https://www.virustotal.com/api/v3/domains/"

    # get a list of subdomains
    def get_subdomains(self, domain):

        # download all subdomains from a domain
        if self.verbose == True:
            self.print("Starting subdomains discovery...")
        self.subdomains = self.download_relationship(domain)

        # check if we got an error
        if self.subdomains is None:
            return None
        
        # return the list of subdomains found
        if self.verbose == True:
            subdomains_count = len(self.subdomains)
            self.print(f"{subdomains_count if subdomains_count > 0 else 'no'} subdomain{'s' if subdomains_count != 1 else ''} found.")
        return self.subdomains

    # download a relationship
    def download_relationship(self, domain):

        # download the first domain page
        results = self.download_relationship_page(domain)
        if results is None:
            return None
        
        # parse the subdomains from the first page
        subdomains = []
        for subdomain in results['data']:
            if subdomain['id'] not in subdomains:
                subdomains.append(subdomain['id'])

        # return the first page if we do a fast scan
        if self.fast_scan == True:
            return subdomains

        # parse the next page cursor from the first page
        cursor = None
        if 'cursor' in results['meta']:
            cursor = results['meta']['cursor']

        # download pages until there is no next one
        while cursor is not None:

            # download the next domain page
            results = self.download_relationship_page(domain, cursor=cursor)
            if results is None:
                break
            
            # parse the subdomains from the next page
            for subdomain in results['data']:
                if subdomain['id'] not in subdomains:
                    subdomains.append(subdomain['id'])

            # parse the next page cursor from the next page
            cursor = None
            if 'cursor' in results['meta']:
                cursor = results['meta']['cursor']

        # return a list of all subdomains found
        return subdomains
    
    # download a relationship page
    def download_relationship_page(self, domain, cursor=None, limit=40):
        
        # query the api
        url = self.base_url + f"{domain}/subdomains"
        params = { 'limit': limit }
        if cursor is not None:
            params['cursor'] = cursor
        headers = { 'x-apikey': self.api_key }
        response = self.session.get(url, headers=headers, params=params)

        # check for errors
        if response.status_code == 401:
            if response.text.find("Wrong API key") != -1:
                self.print_error(f"invalid api key.")
            else:
                self.print_error(f"unauthorized.")
            return None
        elif response.status_code == 429:
            self.print_error(f"too many requests.")
            return None
        elif response.status_code != 200:
            self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the json response
        return response.json()


# Shodan api
class Shodan(ModuleApiWithKey):

    # create a shodan object
    def __init__(self, api_key, verbose=True):
        super().__init__(api_key, verbose=verbose)
        self.base_url = "https://api.shodan.io/dns/domain/"
    
    # query a domain information from shodan
    def query_domain(self, domain):

        # query the api
        params = { 'key': self.api_key }
        response = self.session.get(self.base_url + domain, params=params)

        # check for errors
        if response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None
        
        # return the json response
        return response.json()
    
    # parse the query response
    def parse_query_response(self, data, domain):
        subdomains = []
        for subdomain in data["subdomains"]:
            full_subdomain = subdomain + '.' + domain
            if full_subdomain not in subdomains:
                subdomains.append(full_subdomain)
        return subdomains


# Censys api
class Censys(ModuleApiWithAuth):

    # create a censys object
    def __init__(self, app_id, secret, verbose=True, fast=True):
        super().__init__(app_id, secret, verbose=verbose, fast=fast)
        self.base_url = 'https://search.censys.io/api/v2/certificates/search'

    # get the subdomains from a domain
    def get_subdomains(self, domain):

        # get the first page
        if self.verbose == True:
            self.print("Starting subdomains discovery...")
        self.subdomains = []
        response = self.query_domain_page(domain)
        if response is None:
            return self.subdomains
        
        # parse the subdomains from the first pages
        page_count = 1
        page_subdomains = self.parse_query_response(response)
        for subdomain in page_subdomains:
            if subdomain.endswith(domain) == False:
                continue
            if subdomain in self.subdomains:
                continue
            self.subdomains.append(subdomain)

        # check if we are in fast mode
        if self.fast_scan == True:
            return self.subdomains

        # get the next page cursor if any
        cursor = response['result']['links']['next']

        # get all next pages
        while cursor != '' and page_count < 10:
            page_count += 1
            sleep(0.4)
            response = self.query_domain_page(domain, cursor=cursor)
            if response is None:
                break
            page_subdomains = self.parse_query_response(response)
            for subdomain in page_subdomains:
                if subdomain.endswith(domain) == False:
                    continue
                if subdomain in self.subdomains:
                    continue
                self.subdomains.append(subdomain)
            cursor = response['result']['links']['next']
    
        # return the list of subdomains found
        if self.verbose == True:
            subdomains_count = len(self.subdomains)
            self.print(f"{subdomains_count if subdomains_count > 0 else 'no'} subdomain{'s' if subdomains_count != 1 else ''} found.")
        return self.subdomains

    # get a domain page
    def query_domain_page(self, domain, cursor=None):

        # query the api
        headers = { "Content-Type": "application/json" }
        params = {
            "q": domain,
            "per_page": 100,
            "cursor": cursor,
        }
        if cursor is not None:
            params['cursor'] = cursor

        # send the request
        response = self.session.get(self.base_url, headers=headers, params=params, auth=self.auth)
        
        # check for errors
        if response.status_code == 429:
            if self.verbose == True:
                self.print_error("too many requests.")
            return None
        elif response.status_code == 403:
            if self.verbose == True:
                self.print_error(f"forbidden: '{response.text}'.")
            return None
        elif response.status_code != 200:
            if self.verbose == True:
                self.print_error(f"received unknown response code: '{response.status_code}'.")
            return None

        # return the json response
        return response.json()
    
    # parse the subdomains from a query response
    def parse_query_response(self, response):

        # check each certificate from the response
        subdomains = []
        hits = response['result']['hits']
        for certificate in hits:

            # check the common name
            subject_dn = certificate['parsed']['subject_dn']
            infos = subject_dn.split(", ")
            for info in infos:
                if info.startswith("CN=") == True:
                    common_name = info
            subdomain = common_name[3:]
            pos = subdomain.find('*.')
            while pos != -1:
                subdomain = subdomain[pos + 2:]
                pos = subdomain.find('*.')
            if subdomain.find('*') == -1:
                if subdomain not in subdomains:
                    subdomains.append(subdomain)

            # check the alternate names
            alternate_names = certificate['names']
            for subdomain in alternate_names:
                pos = subdomain.find('*.')
                while pos != -1:
                    subdomain = subdomain[pos + 2:]
                    pos = subdomain.find('*.')
                if subdomain.find('*') == -1:
                    if subdomain not in subdomains:
                        subdomains.append(subdomain)

        # return the list of subdomains found
        return subdomains
    

# run the main function if needed
if __name__ == "__main__":
    main()