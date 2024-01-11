import ccxt
import numpy as np
from typing import List, Union
import os
import requests
import math
# from dotenv import load_dotenv
# load_dotenv()

from concurrent.futures import ThreadPoolExecutor

def get_accurate_price_eliminate_outliers(prices_raw: List[Union[None, float]]) -> Union[None, float]:
    if not isinstance(prices_raw, (list, np.ndarray)): return None
    
    if not all(isinstance(x, (int, float)) or x is None for x in prices_raw):
        return None
    
    valid_prices = []
    for price in prices_raw:
        if price is None: continue 
        if price < 0: continue
        if math.isclose(price, 0): continue
        valid_prices.append(price)

    # At least half of the input prices should be valid (not None)
    if len(valid_prices) * 2 < len(prices_raw): return None
    
    median = np.median(valid_prices)
    accurate_prices = []
    for price in valid_prices:
        # Check if the discrepancy is no larger than 1%
        if np.abs(price-median) * 100 <= median: accurate_prices.append(price)

    # More than half of the valid prices should be accurate w.r.t the median
    return np.mean(accurate_prices) if len(accurate_prices) * 2 > len(valid_prices) else None

binance = ccxt.binance()
okx = ccxt.okx()
mexc = ccxt.mexc3()
gateio = ccxt.gateio()
huobi = ccxt.huobi()
cryptocom = ccxt.cryptocom() # This one doesn't seem to work well
binance_futures = ccxt.binanceusdm() 
exchanges = [binance, okx, mexc, gateio, huobi]
for exchange in exchanges: exchange.timeout = 3000 # 3 seconds

def get_price_from_cex(token_symbol, perpetual=False) -> Union[None, float]:
    def get_price_ccxt(exchange, pair_symbol):
        try:
            price = exchange.fetch_ticker(pair_symbol)['last']
        except: return None
        else: return price

    pair_symbol = token_symbol + "/USDT:USDT" if perpetual else token_symbol + "/USDT"
    prices_raw = []
    with ThreadPoolExecutor(max_workers=len(exchanges)) as executor:
        prices_raw = list(executor.map(lambda ex: get_price_ccxt(ex, pair_symbol), exchanges))
    
    return get_accurate_price_eliminate_outliers(prices_raw)

def get_price_from_dex(token_symbol: str, token_address: str) -> Union[None, float]:
    if (token_symbol == "Unibot"): print("here")

    def get_price_from_moralis(token_symbol: str, token_address: str) -> Union[None, float]:
        # from moralis import evm_api
        # result = evm_api.token.get_token_price(
        #     api_key=api_key,
        #     params=params,
        # )

        api_key = os.getenv("MORALIS_API_KEY")
        api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImFhOWY3Y2Q1LTgyODYtNDczOC04ZTgwLThhZTM1Y2ZmZjBhYyIsIm9yZ0lkIjoiMzYyOTM3IiwidXNlcklkIjoiMzczMDA2IiwidHlwZUlkIjoiY2YxMzcxMjktMmUwOC00ODU3LWE5NDAtNWJkMmIwNDdjNzdkIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE2OTg4MjgwOTEsImV4cCI6NDg1NDU4ODA5MX0.d2fKVH_fIksFgYCVUg4w9tWUmEpHQ6cL1512CP3ZwOQ"
        
        params = {
            "address": token_address,
            "chain": "eth"
        }

        headers = {
            "x-api-key": api_key
        }

        try:
            res = requests.get("https://deep-index.moralis.io/api/v2.2/erc20/:address/price", params=params, headers=headers, timeout=3)
            price = float(res.json()['usdPrice'])
        except: return None
        else: return price

    def get_price_from_coingecko(token_symbol: str, token_address: str) -> Union[None, float]:
        # def is_eth_address(address):
        #     return False if address is None else True

        # if is_eth_address(token_address):
            # ?contract_addresses=0x2260fac5e5542a773aa44fbcfedf7c193bc2c599&vs_currencies=usd
        
        url = "https://api.coingecko.com/api/v3"
        try:
            id_res = requests.get(url+"/search?query="+token_symbol, timeout=3)
            id = id_res.json()["coins"][0]["id"]
            price_res = requests.get(url+"/simple/price?"+"ids="+id+"&"+"vs_currencies="+"usd", timeout=3)
            price = price_res.json()[id]["usd"]
        except: return None
        else: return float(price)

    def get_price_from_cmc(token_symbol: str, token_address: str) -> Union[None, float]:
        """Get last price from coinmarketcap"""
       
        url = "https://web-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest" 
        params = {
            "symbol": token_symbol,
            "convert": "USD",
            "aux": "",
            "skip_invalid": "true",
        }
        try:
            resp = requests.get(url, timeout=3, params=params)
            resp_json = resp.json()
            price = 0.0
            for data in resp_json["data"][token_symbol]:
                # if "platform" not in data or (not data["platform"]): continue
                # if "token_address" not in data["platform"] or (not data["platform"]["token_address"]): continue
                # if data["platform"]["token_address"].lower() == token_address.lower():
                #     price = data["quote"]["USD"]["price"]
                #     break
                price = data["quote"]["USD"]["price"]
        except: return None
        else: return float(price)

    with ThreadPoolExecutor(max_workers=len(exchanges)) as executor:
        prices_raw = list(executor.map(lambda f: f(token_symbol, token_address), \
                                       [get_price_from_moralis, get_price_from_coingecko, get_price_from_cmc]))
    
    if (token_symbol == "Unibot"): print(prices_raw)

    return get_accurate_price_eliminate_outliers(prices_raw)

def get_price(token_symbol: str, token_address: str, perpetual=False) -> Union[None, float]:
    if perpetual:
        cex_perp_price = get_price_from_cex(token_symbol, perpetual)
        if cex_perp_price is not None: return cex_perp_price
    
    cex_spot_price = get_price_from_cex(token_symbol)
    if cex_spot_price is not None: return cex_spot_price

    dex_price = get_price_from_dex(token_symbol, token_address)   
    return dex_price

tokens = [("Unibot", "0xf819d9cb1c2a819fd991781a822de3ca8607c3c9"), \
          ("BTC", ""), \
          ("WETH","0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"), \
          ("ETH", "")]

if __name__ == "__main__": 
    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        prices_accurate = list(executor.map(lambda arg : get_price(*arg), tokens))
        for i in range(len(tokens)):
            print(tokens[i][0], prices_accurate[i])