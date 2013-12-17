### Profile
This project provides a http proxy pool for use when you want a http proxy
server. All proxies which could be retrieved from Internet pages or from other
approaches could be managed by the `ProxyPool` class and the class offers a
unified interface to get one proxy or many.  
This project utilizes **redis** to store proxies, uses **gevent** to retrieve
proxies from Internet pages and to validate the usability of those proxies, so
it could be very fast to get one proxy or many from the database and to validate
proxies in the database.  
And this project uses **yaml** to manage the configuratoin file, which is very
expressive and easy to learn and to use. You could change the default
configuration very easily, add new pages which contains proxies and
corresponding rules for parsing the pages to retrieve the proxies without much
difficulty.

### Services the project offers
The `ProxyPool` class offers such services:

* Get one http proxy or many according to the response time of the proxy
  randomly  
* Retrieve proxies from Internet very fast (based on the functionality of
  **gevent**)
* Validate proxies in the database very fast

### Dependency
This project depends these:

* python requests
* pyaml
* pyredis
* lxml
* gevent  
* redis server

### Usage
1. Edit `settings.yaml` and add sites including proxies in the `PROXY_SITES`
field.
2. Use `ProxyPool().crawl_proxies()` to retrieve proxies from Internet.
3. Use `ProxyPool().validate_proxies()` to validate the availability of proxies
retrieved.
4. Use `ProxyPool().get_one()` or `ProxyPool().get_many()` to get a proxy from
the local database.

### An example to implement a proxy server
Here is an example to implement a proxy server which uses **Nginx** as a reverse
proxy server to provide a unified proxy address and uses **Gunicorn** server to
handle the requests that *Nginx* transfers to.
According to [Gunicorn](http://gunicorn.org/), do the following operations:

1 modify Nginx conf file and add the following:  

```python
srever {
  listen 9000;
  servername localhost;

  location / {
    proxy_pass http://127.0.0.1:8000;
	proxy_set_header Host $host;
	proxy_set_header X-Real-IP $remote_addr;
	proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

2 write a handler to handle the request:  
Assume that the file is `/home/flyer/myapp/app.py` and the contents are:

```python
#coding: utf-8

"""Uses proxies to crawl the Internet.
"""

import requests

from proxypool import ProxyPool

def myhandler(env, start_response):
	proxy_pool = ProxyPool()
	a_proxy = proxy_pool.get_one()

	url_scheme = env['wsgi.url_scheme']
	host = env['HTTP_HOST']
	path = env['RAW_URI']
	url = '%s://%s%s' % (url_scheme, host, path)
	proxies = {'http': a_proxy,}
	res = requests.get(url, proxies=proxies)

	start_response("200 OK", [
	  ('Content-Type', 'text/plain'),
	])

	return 'Hi, this is just a test and the content is %s' % (res.content,)
```

3 run Gunicorn server:  

```shell
$ cd /home/flyer/myapp
$ gunicorn -w 4 -k gevent app:myhandler
```

4 test:  
In *ipython*, execute the following statements:

```python
[1] import requests
[2] proxies = {'http': 'http://localhost:9000'}
[3] url = 'http://www.baidu.com'
[4] res = resquests.get(url, proxies=proxies)
[5] res.content # to see if it starts with the statement 'Hi, this is just a test ....' 
```

<br>
If you want to learn more about *proxy server* and you could read in Chinese,
my blog
[proxy server 简述](http://flyer103.diandian.com/post/2013-12-03/40060317449)
may do you a favor.
