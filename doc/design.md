### 整体设计
分成两部分:

1、proxy pool
分三层:

* 从网上抓取免费的 http 代理，存入 redis 中，采用 sets 数据结构存储  
* 验证抓取到的代理是否是匿名代理，存入 redis 中，采用 sets 数据结构存储
* 验证匿名代理的访问延迟，存入 redis 中，采用 sorted sets 数据结构存储 

2、http 服务
采用 nginx + tornado + proxypool 形式:

* nginx 提供统一的访问接口，并提供负载均衡功能
* tornado 处理 nginx 传来的请求，从 proxypool 中按要求取出代理列表并返回
* proxypool 向 tornado 提供匿名代理列表 
