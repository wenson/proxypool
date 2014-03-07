### API 使用文档
#### 请求方法
通过 HTTP POST 方法请求 http://127.0.0.1:9000/proxylist， post 的数据为:

* target (optional)  
  目标站点，表示需要访问这个网站的最佳代理列表，当前存储的有 baidu、58、ganji，
  若该字段为空或非预定义的几个站点，则返回访问 baidu 最佳的代理列表。  
* num (optional)  
  需要的代理数目，默认 10 个。若 proxy pool 中满足要求的代理少于请求的数目，则返
  回的代理数目会少于请求的数目。  
* delay (optional)  
  要求代理的延迟时间，单位是秒，默认 10s。

示例：

* 无 post 数据  
  返回访问 baidu 最佳的 10 个代理，访问 baidu 的延迟在 10s 内。  
* target=baixing  
  返回访问 baidu 最佳的 10 个代理，访问 baidu 的延迟在 10s 内(因为配置中不存在对
  访问 baixing 的配置)。  
* target=58  
  返回访问 58 最佳的 10 个代理，访问 58 的延迟在 10s 内。  
* ...  
  组合搭配 target、num、delay 返回满足这些需求的代理列表。  

### 返回数据
都是 json 格式的数据。  
共有三种状态:  
1、成功获取代理列表，且 target 站点在默认的配置中

```javascript
{
  "status": "success",
  "proxylist": {
    "target": "ganji",
	"num": 3,
	"proxies": [
	  "http://120.197.85.182:18253",
	  "http://222.87.129.29:80",
	  "http://122.96.59.103:80",
	],
  },
}
```

2、成功获取代理列表，但 target 站点不在默认的配置中
下述的 "success-partial" 表示返回的代理列表对目标站点可能部分可用。 

```javascript
{
  "status": "success-partial",
  "proxylist": {
    "target": "ganji",
	"num": 3,
	"proxies": [
	  "http://120.197.85.182:18253",
	  "http://222.87.129.29:80",
	  "http://122.96.59.103:80",
	],
  },
}
```

3、失败
```javascript
{
  "status": "failure",
  "err": "失败原因",
  "target": "目标站点",
}
```
