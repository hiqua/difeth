#!/usr/bin/env python3
"""
addresses are used as strings

XXX: mirror etherscan locally
"""
import difflib
import logging
import os
import urllib.request
from functools import lru_cache, partialmethod
import itertools
from pprint import pprint

from bs4 import BeautifulSoup

from cache import always_cache
from solc import compile_source
from solc.exceptions import SolcError

verified_url = "https://etherscan.io/contractsVerified"


@lru_cache(maxsize=None)
def fetch(url):
    """Fetch and decode the url
    """
    # logging.debug("Fetching url: {}".format(url))
    logging.debug("Fetching url: %s", url)
    request = urllib.request.Request(url)
    request.add_header('User-Agent',
                       'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)')
    url_fs = urllib.request.urlopen(request)
    return url_fs.read().decode("utf8")


def same_code(a_src, b_src):
    """Returns whether a_src and b_src have the same code by compiling them.

    On compiler failure, assume they are different.
    """
    try:
        return compile_source(a_src) == compile_source(b_src)
    except SolcError:
        logging.debug("Failure to compile using solc.")
        return False


def extract_code(address):
    """Extract the code for one address
    """
    url = "https://etherscan.io/address/{}#code".format(address)
    content = fetch(url)
    soup = BeautifulSoup(content, 'html.parser')
    soli_code = soup.find(id='editor')
    if soli_code is None:
        raise ValueError("Solidity code not found")
    return soli_code.getText().replace("\r", "")


def extract_solidity_code(addresses):
    """Extract solidity code from addresses

    Return a dict addr => code
    """
    code = dict()
    for addr in addresses:
        try:
            code[addr] = extract_code(addr)
        except ValueError:
            logging.info("Solidity code not found for %s, skipping", addr)

    return code


def nb_verified():
    """Get the current page number and the number of pages of verified contracts
    """
    content = fetch(verified_url)
    soup = BeautifulSoup(content, 'html.parser')
    numbers = soup.find(id="ContentPlaceHolder1_PagingPanel")
    curr_page = int(numbers.findChildren()[4].getText())
    total_page = int(numbers.findChildren()[5].getText())
    return (curr_page, total_page)


def extract_address_tags(url):
    """Extract the addresses in the address-tag
    """
    content = fetch(url)
    soup = BeautifulSoup(content, 'html.parser')
    return set(ad.getText()
               for ad in soup.findAll(class_="address-tag"))


def fetch_addresses_verified():
    """Return the list of adresses of verified contracts
    """
    def get_ad_on_page(i):
        """Extract addresses on page i of verified contracts
        """
        url = verified_url + "/{}".format(i)
        return extract_address_tags(url)

    _, total_page = nb_verified()

    res = set()
    for i in range(total_page):
        res.update(get_ad_on_page(i))

    return res


def compute_diff(a_src, b_src):
    """Compute diff between a_src and b_src given as strings
    """
    return ''.join(
        difflib.unified_diff(
            a_src.splitlines(keepends=True),
            b_src.splitlines(keepends=True)))


def find_similar(addr):
    """Return the addresses of similar contracts
    """
    assert isinstance(addr, str), type(addr)
    logging.debug("Finding contracts similar to %s", addr)
    base_url = "https://etherscan.io/find-similiar-contracts?a="
    url = base_url + addr
    return extract_address_tags(url)


def find_similar_contracts(addresses):
    """Return the list of addresses of similar contracts for

    Url is base_url + address
    """
    similar = dict()
    for addr in addresses:
        similar[addr] = find_similar(addr)

    return similar


def write_diff(ref_addr, ref_code, sim_addr, sim_code, folder="diffs"):
    """Write diff given the code
    """
    diff = compute_diff(ref_code, sim_code)
    if diff:
        curr_folder = os.path.join(folder, ref_addr)
        os.makedirs(curr_folder, exist_ok=True)

        with open(os.path.join(curr_folder, "{}_code".format(ref_addr)),
                  'w') as fs:
            fs.write(ref_code)

        with open(os.path.join(curr_folder, sim_addr), 'w') as fs:
            logging.debug("Writing diff in %s", curr_folder)
            fs.write(diff)


def process_addr(ref_addr, similar_addresses):
    """Take a reference address and similar ones and write the diffs
    """
    ref_code = extract_code(ref_addr)
    similar_codes = dict()
    for addr in similar_addresses:
        similar_codes[addr] = extract_code(addr)

    for addr in similar_codes:
        write_diff(ref_addr=ref_addr,
                   ref_code=ref_code,
                   sim_addr=addr,
                   sim_code=similar_codes[addr])


def main(starting_addr=None, ending_addr=3, folder="diffs"):
    """The main function

    _Retrieve nb_addr verified contracts
    _Retrieve related contracts
    _Compute the diffs
    _Save the diffs in the "diffs" folder

    Args:
        nb_addr: the number of addresses to use

    """
    verified_addresses = always_cache(fetch_addresses_verified)

    # addresses is a sorted list to be deterministic
    addresses = sorted(verified_addresses)

    if starting_addr is None:
        starting_addr = 0
    if ending_addr is None:
        ending_addr = len(addresses)

    addresses = itertools.islice(addresses,
                                 starting_addr,
                                 ending_addr)
    nb_addr = ending_addr - starting_addr

    logging.info("Using %s addresses", nb_addr)

    for i, addr in enumerate(addresses):
        logging.info("Processing address number %s / %s",
                     i + 1,
                     nb_addr)
        similar_addresses = find_similar(addr) & verified_addresses
        process_addr(ref_addr=addr,
                     similar_addresses=similar_addresses)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    logging.info("Starting")

    # try with 600, should take less than 4 hours
    step = 100
    for i in range(0, 3000, step):
        logging.info("%s addresses processed", i)
        main(starting_addr=i,
             ending_addr=i+step)
    logging.info("Ending")
