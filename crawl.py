#!/usr/bin/env python3
"""
Crawl ethscan to find verified (i.e. with solidity code provided) contracts and
similar contracts, compute the diffs and save them locally.
addresses are used as strings
"""
import difflib
import itertools
import logging
import os
from multiprocessing import Pool
import OpenSSL

import urllib3.contrib.pyopenssl


import requests
from bs4 import BeautifulSoup

from cache import cache_func_and_arg
from cachecontrol import CacheControl
from solc import compile_source
from solc.exceptions import SolcError

VERIFIED_URL = "https://etherscan.io/contractsVerified"

urllib3.contrib.pyopenssl.inject_into_urllib3()
SESSION = CacheControl(requests.session())


def fetch(url, nb_attempts=5):
    """Fetch the url

    From time to time, the ssl modules raises SSLError for some reason.
    Retrying usually works as a workaround, so we do that.
    """
    def _fetch():
        request = SESSION.get(url)
        if not request:
            logging.warning("Got status code: %s", request.status_code)
        request.raise_for_status()
        return request.text

    for _ in range(nb_attempts):
        try:
            res = _fetch()
        except (OpenSSL.SSL.Error,
                requests.exceptions.RequestException) as e:
            logging.warning(e)
        else:
            return res

    logging.error('Page %s could not be fetched, returning ""', url)
    return ""


def same_code(a_src, b_src):
    """Whether a_src and b_src have the same code by compiling them.

    On compiler failure, assume they are different.

    Args:
        a_src: the first source code.
        b_src: the second source code.

    Return:
        a boolean that says whether the source code are equivalent.
    """
    try:
        res = compile_source(a_src) == compile_source(b_src)
    except SolcError:
        logging.debug("Failure to compile using solc.")
        return False
    else:
        return res


@cache_func_and_arg
def extract_code(address):
    """Extract the Solidity code for one verified address.

    Args:
        address: the ETH address to extract code from.

    Returns:
        the Solidity code of this address.

    Raises:
        ValueError: if the Solidity code could not be extracted.
    """
    url = "https://etherscan.io/address/{}#code".format(address)
    content = fetch(url)
    soup = BeautifulSoup(content, 'html.parser')
    soli_code = soup.find(id='editor')
    if soli_code is None:
        raise ValueError("Solidity code not found for: {}".format(address))
    return soli_code.getText().replace("\r", "")


def extract_solidity_code(addresses):
    """Extract solidity code from addresses.

    Args:
        addresses: an iterator of addresses

    Returns:
        a dict mapping an address to its code, if found.
    """
    code = dict()
    for addr in addresses:
        try:
            res = extract_code(addr)
        except ValueError as e:
            logging.info("%s", str(e))
        else:
            code[addr] = res

    return code


def nb_verified():
    """Get the current page number and the number of pages of verified contracts
    """
    content = fetch(VERIFIED_URL)
    soup = BeautifulSoup(content, 'html.parser')
    numbers = soup.find(id="ContentPlaceHolder1_PagingPanel")
    curr_page = int(numbers.findChildren()[4].getText())
    total_page = int(numbers.findChildren()[5].getText())
    return (curr_page, total_page)


@cache_func_and_arg
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
        url = VERIFIED_URL + "/{}".format(i)
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
    res = extract_address_tags(url)
    logging.debug("Found %s similar addresses", len(res))
    return res


def find_similar_contracts(addresses):
    """Return the list of addresses of similar contracts for

    Url is base_url + address.
    """
    similar = dict()
    for addr in addresses:
        similar[addr] = find_similar(addr)

    return similar


def write_diff(ref_addr, ref_code, sim_addr, sim_code, folder):
    """Write diff given the code
    """
    diff = compute_diff(ref_code, sim_code)

    if not diff:
        logging.debug("Same code, the diff will not be written.")
        return

    curr_folder = os.path.join(folder, ref_addr)
    os.makedirs(curr_folder, exist_ok=True)

    ref_code_fn = os.path.join(curr_folder, "{}_code".format(ref_addr))

    with open(ref_code_fn, 'w') as ref_code_fs:
        ref_code_fs.write(ref_code)

    with open(os.path.join(curr_folder, sim_addr), 'w') as sim_fs:
        logging.debug("Writing diff in %s", curr_folder)
        sim_fs.write(diff)


def process_addr(ref_addr, verified_addresses, i, nb_addr, folder):
    """Take a reference address and similar ones and write the diffs.
    """
    logging.info("Processing address number %s / %s", i + 1, nb_addr)
    similar_addresses = find_similar(ref_addr) & verified_addresses

    def safe_extract_code(addr):
        """Extract code with throwing exception
        """
        try:
            code = extract_code(addr)
        except ValueError as e:
            logging.warning("%s", str(e))
        else:
            return code

    ref_code = safe_extract_code(ref_addr)
    if ref_code is None:
        return

    similar_codes = dict()
    for addr in similar_addresses:
        sim_code = safe_extract_code(addr)
        if sim_code is None:
            continue
        similar_codes[addr] = sim_code

    for addr in similar_codes:
        write_diff(ref_addr=ref_addr,
                   ref_code=ref_code,
                   sim_addr=addr,
                   sim_code=similar_codes[addr],
                   folder=folder)


def main(starting_addr=None, ending_addr=3, folder="diffs", parallel=True):
    """The main function

    _Retrieve nb_addr verified contracts
    _Retrieve related contracts
    _Compute the diffs
    _Save the diffs in the "diffs" folder

    Args:
        nb_addr: the number of addresses to use

    """
    verified_addresses = fetch_addresses_verified()

    # addresses is sorted for determinism
    addresses = sorted(verified_addresses)

    if starting_addr is None:
        starting_addr = 0

    if ending_addr is None:
        ending_addr = len(addresses)

    addresses = list(itertools.islice(addresses,
                                      starting_addr,
                                      ending_addr))
    nb_addr = len(addresses)

    logging.info("Using %s addresses", nb_addr)

    if parallel:
        with Pool(2) as pool:
            pool.starmap(process_addr,
                         [(ref_addr, verified_addresses, i, nb_addr, folder)
                          for i, ref_addr in enumerate(addresses)])
    else:
        for i, ref_addr in enumerate(addresses):
            process_addr(ref_addr, verified_addresses, i, nb_addr, folder)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.INFO)
    logging.info("Starting")

    STEP = 100
    for starting_addr_ in range(0, 3000, STEP):
        logging.info("%s addresses processed", starting_addr_)
        main(starting_addr=starting_addr_,
             ending_addr=starting_addr_ + STEP,
             parallel=True)
    logging.info("Ending")
