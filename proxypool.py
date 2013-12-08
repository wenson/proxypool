#coding: utf-8

"""Provide a proxy pool

Proxies retrieved from the Internet or other approaches are
stored in redis #3 database, using the 'sorted sets' format.
"""

import os
import time
import random
import logging

import requests
import yaml
import redis
import gevent
from gevent.pool import Pool, Group
from gevent.timeout import Timeout
from gevent import monkey
from lxml import etree

monkey.patch_all(thread=False, select=False)

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s][%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


class ProxyPool(object):
    """Proxy Pool.
    """
    def __init__(self, configfile='settings.yaml'):
        self.configs     = self._get_configs(configfile)
        self.rdb         = redis.StrictRedis(db=self.configs['RDB'])
        self.db_zproxy   = self.configs['DB_ZPROXY']
        self.pool        = Pool(self.configs['MAX_CONCURRENCY'])
        self.group       = Group()
        self.wrong_value = self.configs['WRONG_VALUE']
        self.init_value  = self.configs['INIT_VALUE']

    def _get_configs(self, configfile):
        """Return the configuration dict"""
        # XXX: getting the path of the configuraion file needs improving
        configpath = os.path.join('.', configfile)
        with open(configpath, 'rb') as fp:
            configs = yaml.load(fp)

        return configs

    def get_many(self, num=3, minscore=0, maxscore=None):
        """
        Return a list of proxies including at most 'num' proxies
        which socres are between 'minscore' and 'mascore'.
        If there's no proxies matching, return an empty list.
        """
        minscore = minscore
        maxscore = maxscore or self.init_value
        res = self.rdb.zrange(self.db_zproxy, minscore, maxscore)
        if res:
            random.shuffle(res) # for getting random results
            if len(res) < num:
                logging.warning("The number of proxies you want is less than %d"
                                % (num,))
            return [proxy for proxy in res[:num]]
        else:
            logging.warning("There're no proxies which scores are between %d and %d"
                            % (minscore, maxscore))
            return []

    def get_one(self, minscore=0, maxscore=None):
        """
        Return one proxy which score is between 'minscore'
        and 'maxscore'.
        If there's no proxy matching, return an empty string.
        """
        minscore = minscore
        maxscore = maxscore or self.init_value
        res = self.get_many(num=1, minscore=minscore, maxscore=maxscore)
        if res:
            return res[0]
        else:
            return ''

    def crawl_proxies(self):
        """Get proxies from vairous methods.
        """
        statics = []
        self._crawl_proxies_sites(statics=statics)
        logging.info('Having add %d proxies' % (len(statics),))

    def _crawl_proxies_sites(self, statics=[]):
        """Get proxies from web pages."""
        args = ((url, val['rules'], val['proxies'], statics)
                for url, val in self.configs['PROXY_SITES'].iteritems())
        self.pool.map(self._crawl_proxies_one_site, args)

    def _crawl_proxies_one_site(self, args):
        """Get proxies (ip:port) from url and then write them into redis."""
        url             = args[0]
        rules           = args[1]
        proxies         = args[2]
        headers         = self.configs['HEADERS']
        headers['Host'] = url.split('/', 3)[2]
        logging.info('Begin crawl page %s' % (url,))
        res             = requests.get(url, headers=headers, proxies=proxies)
        encoding        = res.encoding
        html            = etree.HTML(res.content)
        proxies         = []
        len_rules       = len(rules)

        nodes = html.xpath(rules[0])
        if nodes:
            if len_rules == 1:
                for node in nodes:
                    text = str(node.text).encode(encoding).strip()
                    if text:
                        proxies.append('http://%s' % (text,))
            elif len_rules == 2:
                rule_1 = rules[1].split(',')
                for node in nodes:
                    node = node.xpath(rule_1[0])
                    ip = str(node[1].text).encode(encoding).strip()
                    port = str(node[2].text).encode(encoding).strip() or '80'
                    if ip:
                        proxies.append('http://%s:%s' % (ip, port))

        for proxy in proxies:
            logging.info('Get proxy %s from %s' % (proxy, url))
            args[3].append(proxy)
            self.rdb.zadd(self.db_zproxy, self.init_value, proxy)

    def validate_proxies(self):
        """Validate whether the proxies are alive."""
        maxscore       = self.init_value + self.wrong_value
        proxies        = self.rdb.zrange(self.db_zproxy, 0, maxscore)
        statics_errors = []
        args           = [(proxy, statics_errors) for proxy in proxies]
        self.group.map(self._validate_one_proxy, args)

        logging.info('Have validated %d proxies, %d errors happened.'
                     % (len(proxies), len(statics_errors)))

    def _validate_one_proxy(self, args):
        """Validate whether the proxy is still alive."""
        test_sites = self.configs['TEST_SITES']
        proxy      = args[0]
        time_res   = []
        args       = [(site, proxy, time_res, args[1]) for site in test_sites]
        self.group.map(self._test_one_site, args)

        mean_time = sum(time_res) / len(test_sites)
        logging.info('Validating %s, score is %d' % (proxy, mean_time))
        self.rdb.zadd(self.db_zproxy, mean_time, proxy)

    def _test_one_site(self, args):
        url             = args[0]        
        headers         = self.configs['HEADERS']
        headers['Host'] = url.split('/', 3)[2]
        proxy           = args[1]
        proxies         = {'http': proxy,}
        start_time      = time.time()
        timeout         = self.configs['TEST_TIMEOUT']
        error           = False
        with Timeout(timeout, False):
            try:
                res = requests.get(url, headers=headers, proxies=proxies)
            except Exception as e:
                error = True
                logging.error('%s: Error: %s' % (proxy, e.message))

        if error:
            args[2].append(self.configs['WRONG_VALUE'])
            args[3].append(proxy)
        else:
            args[2].append(time.time() - start_time)
        
