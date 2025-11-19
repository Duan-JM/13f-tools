#!/bin/bash

# SEC 网站访问测试脚本
# 使用完整的浏览器请求头来避免403错误

echo "🔍 测试 SEC 网站访问..."

# 测试基本搜索页面
echo "1. 测试基本搜索功能..."
curl -s -w "状态码: %{http_code}\n" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ValueAnalyze-Research-SEC13F-Analyzer/1.0 (research@valueanalyze.com)" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" \
  -H "Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7" \
  -H "Accept-Encoding: gzip, deflate, br" \
  -H "Cache-Control: no-cache" \
  -H "Pragma: no-cache" \
  -H "Sec-Ch-Ua: \"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"" \
  -H "Sec-Ch-Ua-Mobile: ?0" \
  -H "Sec-Ch-Ua-Platform: \"macOS\"" \
  -H "Sec-Fetch-Dest: document" \
  -H "Sec-Fetch-Mode: navigate" \
  -H "Sec-Fetch-Site: none" \
  -H "Sec-Fetch-User: ?1" \
  -H "Upgrade-Insecure-Requests: 1" \
  -H "Connection: keep-alive" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=Berkshire&type=13F&dateb=&count=40" \
  | head -20

echo ""
echo "2. 测试伯克希尔哈撒韦CIK查询..."
curl -s -w "状态码: %{http_code}\n" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ValueAnalyze-Research-SEC13F-Analyzer/1.0 (research@valueanalyze.com)" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" \
  -H "Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7" \
  -H "Accept-Encoding: gzip, deflate, br" \
  -H "Cache-Control: no-cache" \
  -H "Pragma: no-cache" \
  -H "Sec-Ch-Ua: \"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"" \
  -H "Sec-Ch-Ua-Mobile: ?0" \
  -H "Sec-Ch-Ua-Platform: \"macOS\"" \
  -H "Sec-Fetch-Dest: document" \
  -H "Sec-Fetch-Mode: navigate" \
  -H "Sec-Fetch-Site: none" \
  -H "Sec-Fetch-User: ?1" \
  -H "Upgrade-Insecure-Requests: 1" \
  -H "Connection: keep-alive" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001067983&type=13F&dateb=&count=10" \
  | head -20

echo ""
echo "✅ 测试完成！如果看到HTML内容而非403错误，说明请求头配置正确。"
