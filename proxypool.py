#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------
# Author: zhangyifei <zhangyifei@baixing.com>
# Date: 2014-03-04
# -----------------------------------------

"""代理池服务.

NOTE:
  + 当前提供匿名 http 代理
  + etree.HTML() 传入数据时，传入 str 类型的，不要传入 bytes 类型的, 例：
    - etree.HTML(requests.get('http://www.baidu.com').text)
  + Redis 是单线程的，线程安全，故多线程操作时不需要锁

TODO:

Thinking:
  + gevent 不支持 python3.x，不能使用
  + asyncio 虽然可以用 coroutine，但由于没有配合的 http library，也不能发挥作用
  + 暂时通过多线程控制并发

!!!:
  + redis 是通过 socket 连接，存在一个最大连接数问题，两种解决方法:
    - 通过 ｀ulimit -n 数字｀来解决
    - 随机 sleep 几秒后重连 redis
  + 58 和 赶集 对代理封的比较狠
"""

import os
import sys
import time
import random
import pprint
import logging
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

import requests
import yaml
import redis
from lxml import etree

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s][%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


class ProxyPool(object):
    """代理池.
    """
    def __init__(self, configfile='settings.yaml'):
        self.configs        = self._get_configs(configfile)
        
        self.rdb            = redis.StrictRedis(db=self.configs['STORE']['RDB'])
        self.try_times_db   = self.configs['STORE']['TRY']
        self.try_time_wait  = self.configs['STORE']['TIME_WAIT']
        self.sproxy_all     = self.configs['STORE']['SPROXY_ALL']
        self.sproxy_anon    = self.configs['STORE']['SPROXY_ANON']
        self.init_value     = self.configs['VALIDATE']['INIT_VALUE']
        self.timeout_valid  = self.configs['VALIDATE']['TIMEOUT_VALID']
        self.time_exception = self.configs['VALIDATE']['TIME_EXCEPTION']
        self.targets        = list(self.configs['TARGET'].keys())
        self.url_reflect    = self.configs['URL']['REFLECT']

        self.tnum_proxy_getter = self.configs['CONCURRENT']['PROXY_GETTER']
        self.tnum_proxy_filter = self.configs['CONCURRENT']['PROXY_FILTER']
        self.tnum_proxy_valid  = self.configs['CONCURRENT']['PROXY_VALID']

    def _get_configs(self, configfile):
        """Return the configuration dict"""
        # XXX: getting the path of the configuraion file needs improving
        configpath = os.path.join('.', configfile)
        with open(configpath, 'rb') as fp:
            configs = yaml.load(fp)

        return configs

    def get_mtime(self, target='all'):
        """返回代理上次更新时间"""
        target = str(target).upper()
        if target not in self.targets:
            target = 'ALL'

        db_mtime = self.configs['TARGET'][target]['DB_MTIME']
        mtime    = self.rdb.get(db_mtime)

        return int(mtime)

    def get_many(self, target='all', num=10, minscore=0, maxscore=None):
        """
        Return a list of proxies including at most 'num' proxies
        which socres are between 'minscore' and 'mascore'.
        If there's no proxies matching, return an empty list.
        """
        # XXX: 当前的策略是先从数据库中取出所有满足要求的代理，然后返回指定数目的代理.
        #      个人觉得这种策略有待改善，还有优化的空间.
        target = str(target).upper()
        if target not in self.targets:
            target = 'ALL'

        db       = self.configs['TARGET'][target]['DB_PROXY']
        num      = num
        minscore = minscore
        maxscore = maxscore or self.init_value
        res      = self.rdb.zrangebyscore(db, minscore, maxscore)
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

    def get_one(self, target='all', minscore=0, maxscore=None):
        """
        Return one proxy which score is between 'minscore'
        and 'maxscore'.
        If there's no proxy matching, return an empty string.
        """
        target   = target
        minscore = minscore
        maxscore = maxscore or self.init_value
        res      = self.get_many(target=target, num=1, minscore=minscore, maxscore=maxscore)
        
        if res:
            return res[0]
        else:
            return ''

    def fetch_proxies(self):
        """Get proxies from vairous methods."""
        # 从网页获得
        self._crawl_proxies_sites()

    def _crawl_proxies_sites(self):
        """Get proxies from web pages."""
        with ThreadPoolExecutor(max_workers=self.tnum_proxy_getter) as executor:
            for url, val in self.configs['PROXY_SITES'].items():
                executor.submit(self._crawl_proxies_one_site, url, val['rules'], val['proxies'])
        
    def _crawl_proxies_one_site(self, url=None, rules=None, proxies=None):
        # Get proxies (ip:port) from url and then write them into redis.
        # XXX: 抓取和解析分离
        url     = url
        rules   = rules
        proxies = proxies
        headers = self.configs['CRAWL']['HEADERS']
        logging.info('Begin crawl page %s' % (url,))
        
        res       = requests.get(url, headers=headers, proxies=proxies)
        encoding  = res.encoding
        html      = etree.HTML(res.text)
        proxies   = []
        len_rules = len(rules)

        nodes = html.xpath(rules[0])
        if nodes:
            if len_rules == 1:
                for node in nodes:
                    text = node.text.strip()
                    if text:
                        proxies.append('http://%s' % (text,))
            elif len_rules == 2:
                rule_1     = rules[1].split(',')
                rule_1_len = len(rule_1)

                if rule_1_len == 3:
                    for node in nodes:
                        try:
                            node = node.xpath(rule_1[0])
                            ip   = node[1].text.strip()
                            port = node[2].text.strip() or '80'
                            if ip:
                                proxies.append('http://%s:%s' % (ip, port))
                        except Exception as e:
                            logging.error('Error when parsing %s: %r' % (url, e))
                elif rule_1_len == 4:
                    for node in nodes:
                        try:
                            ip        = node.xpath(rule_1[0])[0].text.strip()
                            port      = node.xpath(rule_1[1])[0].text.strip()
                            is_niming = node.xpath(rule_1[2])[0].text.strip().encode('utf-8')
                            dec       = rule_1[-1].encode('utf-8')

                            if dec == b'proxy360' and ip and is_niming == '高匿':
                                proxies.append('http://%s:%s' % (ip, port))
                            elif dec == b'cn-proxy' and ip and is_niming == '高度匿名':
                                proxies.append('http://%s:%s' % (ip, port))
                        except Exception as e:
                            logging.error('Error when parsing %s: %r' % (url, e))

        for proxy in proxies:
            logging.info('Got proxy %s from %s' % (proxy, url))
            self.rdb.sadd(self.sproxy_all, proxy)

    def get_ip_local(self):
        # 获取本机出口 ip，最多尝试三次，若尝试后都不能获得，就结束整个程序，因为后续不能保证
        # 提供的代理是否匿名可依赖
        timeout   = self.configs['LOCAL_IP']['TIMEOUT']
        try_times = self.configs['LOCAL_IP']['TRY']
        for times_try in range(try_times):
            try:
                headers = self.configs['CRAWL']['HEADERS']
                res     = requests.get(self.url_reflect, headers=headers, timeout=timeout)
                
                ip_local = res.text.split(':')[-1].split("\n")[0].strip().split('"')[1]

                return ip_local
            except Exception:
                logging.debug('Times of trying to get local ip: %d' % (times_try+1,))
        else:
            sys.exit("Fatal error: couldn't get the local ip.")

    def filter_anony(self):
        # 检测抓取到的所有的代理是否是匿名
        # XXX: 需要考虑下面这个循环是否必要
        # while True:
        #     # 等待抓取代理的线程完成
        #     num_active = threading.active_count()
        #     if num_active == 1:
        #         break
        #     else:
        #         logging.debug('Number of active: %d' % (num_active,))
        #         time.sleep(1)

        self.ip_local = self.get_ip_local()
        proxies = self.rdb.smembers(self.sproxy_all)
        self._filter_anony(proxies)
        
    def _filter_anony(self, proxies):
        # 把 proxies 中的匿名代理找出来，proxies 格式是 ['ip:port', 'ip:port', ...]
        with ThreadPoolExecutor(max_workers=self.tnum_proxy_filter) as executor:
            for proxy in proxies:
                executor.submit(self._valid_anony, proxy)

    def _valid_anony(self, proxy):
        # 判断该 proxy 是否是 http 匿名代理，参数 proxy 格式是 'http://ip:port'
        # 策略:
        #     + 若是匿名代理，则加入到 sproxy_anon
        #     + 若非匿名代理，则从 sproxy_anon 删除 (不存在时删除没有影响)
        proxies = {
            'http': proxy.decode('utf-8'),
        }
        
        try:
            headers = self.configs['CRAWL']['HEADERS']
            res = requests.get(self.url_reflect, headers=headers, proxies=proxies, timeout=10)
        except Exception as e:
            logging.error('Error when validating anonymous: %r' % (e,))
            return
            
        if not self.ip_local in res.text:
            logging.info('Anonymous: %s' % (proxy,))
            self.rdb.sadd(self.sproxy_anon, proxy)
        else:
            logging.info('NON-Anonymous: %s' % (proxy,))
            self.rdb.srem(self.sproxy_anon, proxy)
            
    def valid_active(self):
        # 检验所有的匿名代理的可用性
        proxies = self.rdb.smembers(self.sproxy_anon)

        with ThreadPoolExecutor(max_workers=self.tnum_proxy_valid) as executor:
            for target in self.targets:
                for proxy in proxies:
                    executor.submit(self._efficiency_proxy, proxy, target)

    def _efficiency_proxy(self, proxy, target):
        # 通过该代理访问指定的几个站点获取访问时间，来检验一个匿名代理是否存活
        # XXX: 当前是顺序访问指定的站点，考虑是否改为并发访问
        try:
            target = target.upper()
        except AttributeError:
            target = target
        test_site = self.configs['TARGET'][target]['URL']
        db_proxy  = self.configs['TARGET'][target]['DB_PROXY']
        db_mtime  = self.configs['TARGET'][target]['DB_MTIME']        
        validate  = self.configs['TARGET'][target]['VALIDATE']
        
        time_delay = self._timing_proxy(proxy.decode('utf-8'), test_site, val=validate)
        proxy      = proxy.decode('utf-8')
        mtime      = int(time.time())

        try_times = 0
        while True:
            # 尝试三次连接 redis
            try:
                self.rdb.zadd(db_proxy, time_delay, proxy)
                self.rdb.set(db_mtime, mtime)

                logging.info('Have validated %s' % (proxy,))
                
                break
            except Exception as e:
                try_times += 1
                logging.info('Tried %d' % (try_times,))
                if try_times >= self.try_times_db:
                    logging.error(e)
                    break
                time.sleep(random.randint(0, self.try_time_wait))
                self.rdb = redis.StrictRedis(db=self.configs['STORE']['RDB'])                
            
    def _timing_proxy(self, proxy, site, val):
        # 获取通过该代理访问指定站点的耗时
        time_start = time.time()
        
        try:
            res   = requests.get(site, timeout=self.timeout_valid)
            html  = etree.HTML(res.content)
            title = html.xpath("/html/head/title")[0].text
            
            if res.status_code == 200:
                time_end = time.time()
            else:
                logging.error('Error when validating %s' % (proxy,))
                time_end = -1
        except Exception as e:
            logging.error('Error when validating %s: %r' % (proxy, e))
            time_end = -1

        if time_end == -1:
            time_interval = self.time_exception
        else:
            time_interval = time_end - time_start

        return time_interval

        
if __name__ == '__main__':
    proxypool = ProxyPool()
    proxypool.fetch_proxies()   # 抓取代理
    proxypool.filter_anony()    # 挑选出匿名代理
    proxypool.valid_active()    # 验证代理的可用性
    # pprint.pprint(proxypool.get_many(num=3, maxscore=10, target='58'))
    # pprint.pprint(proxypool.get_many(num=3, maxscore=10, target=58))
    # pprint.pprint(proxypool.get_many(num=3, maxscore=10, target='baixing'))
    # pprint.pprint(proxypool.get_many())
