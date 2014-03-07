### 目的
解决抓取站点对访问频率的限制问题，通过匿名代理访问目标站点。

### 功能
通过一个 HTTP API 提供匿名代理列表。

### 配置
1、安装项目的依赖
与 python 相关的依赖 (注意该项目使用 python3.3):

```shell
$ pip3 install -r requirements.txt
```

此外系统中还需要安装 redis-server。  

2、获取验证代理
在项目根目录下，执行:

```shell
$ python3.3 proxypool.py
```

3、配置 nginx
一个简单的 nginx.conf 形式:

```python
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    sendfile        on;

    keepalive_timeout  65;

	upstream frontends {
	    server 127.0.0.1:8000;
		server 127.0.0.1:8001;
		server 127.0.0.1:8002;
		server 127.0.0.1:8003;
		server 127.0.0.1:8004;
	}

	server {
	    listen 9000;
		server_name localhost;

		location / {
			proxy_pass http://frontends;
			proxy_set_header Host $host;
			proxy_set_header X-Real-IP $remote_addr;
			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header X-Forwarded-Proto $scheme;
		}
	}	
}
```

启动 nginx:

```shell
# nginx -t
# nginx &
```

4、启动 handler  
在该项目目录下，运行:

```shell
$ cd handlers
$ python3.3 handler_800* &
```

5、测试
在 chrome 中下载
[Postman](https://chrome.google.com/webstore/detail/postman-rest-client/fdmmgilgnpjigdojojpjoooidkmcomcm?utm_source=chrome-ntp-launcher)
插件，然后通过 POST 方法请求 http://127.0.0.1:9000/proxylist 来查看返回结果。

### 其他文档
1、[API 使用文档](/proxypool/doc/API.md)

2、[项目设计文档](/proxypool/doc/design.md)

### 问题反馈
可随时向我 (zhangyifei@baixing.com) 反馈使用该项目过程中遇到的问题。
