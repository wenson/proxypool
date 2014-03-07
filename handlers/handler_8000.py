#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------
# Author: zhangyifei <zhangyifei@baixing.com>
# Date: 2014-03-04 21:18:55
# -----------------------------------------

"""处理 nginx 传来的请求，返回相应的 proxy list.
"""

import json

import tornado.ioloop
import tornado.web

from proxypool import ProxyPool


class ProxyListHandler(tornado.web.RequestHandler):
    """返回用户需求的代理列表，json 格式
    示例:
    + 成功
    {
      'status': 'success',
      'proxylist': {
        'num': 5,
        'mtime': 1394069326,
        'proxies': [
          'http://220.248.180.149:3128',
          'http://61.55.141.11:81',
          ......,
        ],
      },
    }
      - 若数据库中存储了指定站点的 proxy list，且正确返回，则状态是 success
      - 若数据库中没有存储指定站点的 proxy list，但正确返回，则状态是 success-partial，
        表示返回的代理对指定的站点部分可用
    + 失败
    {
      'status': 'failure',
      'err': '失败原因',
    }
    """
    def get(self):
        self.write('Please refer to the API doc.')
    
    def post(self):
        target = self.get_argument('target', default='') or 'all'
        num    = int(self.get_argument('num', default='') or 5)
        delay  = int(self.get_argument('delay', default='') or 10)

        proxypool = ProxyPool()
        
        try:
            proxies = proxypool.get_many(target=target, num=num, maxscore=delay)
            num_ret = len(proxies)
            mtime   = proxypool.get_mtime(target=target)

            proxylist = []
            for proxy in proxies:
                proxylist.append(proxy.decode('utf-8'))

            if str(target).upper() in proxypool.targets:
                status = 'success'
            else:
                status = 'success-partial'

            ret = {
                'status': status,
                'proxylist': {
                    'num': num_ret,
                    'mtime': mtime,
                    'target': target,
                    'proxies': proxylist,
                },
            }
        except Exception as e:
            ret = {
                'status': 'failure',
                'target': target,
                'err': str(e),
            }

        self.set_header('Content-Type', 'application/json')

        self.write(json.dumps(ret))


class MainHandler(tornado.web.RequestHandler):
    """处理未匹配到的请求"""
    def get(self):
        self.write('Please refer to the API doc.')

    def post(self):
        self.write('Please refer to the API doc.')
        

app = tornado.web.Application([
    (r'/proxylist', ProxyListHandler),
    (r'.*', MainHandler),
])


if __name__ == '__main__':
    app.listen(8000)
    tornado.ioloop.IOLoop.instance().start()
