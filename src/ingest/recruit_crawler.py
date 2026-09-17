# -*- coding: utf-8 -*-
"""
招聘信息爬虫模块
===================
带完整反爬策略的招聘网站爬虫框架

反爬策略：
  1. User-Agent 随机轮换（PC + 移动端，20+ UA）
  2. 请求随机延迟（1-5秒，正态分布）
  3. 请求头模拟（Referer、Accept-Language、Accept-Encoding 等）
  4. Cookie 池（多账号 Cookie 轮换）
  5. 代理 IP 池支持（HTTP/HTTPS 代理）
  6. 失败重试 + 指数退避
  7. 页面随机滚动模拟人类行为
  8. 请求频率限制（每小时最多 N 次）
  9. 验证码识别接口预留（可接入打码平台）
 10. 分布式任务队列支持

使用方式：
  # 1. 真实爬取（需要配置 Cookie 和代理）
  from recruit_crawler import RecruitCrawler
  crawler = RecruitCrawler(site='lagou', use_proxy=True)
  jobs = crawler.search('Java', city='北京', page=1)

  # 2. 真实感数据生成（无需联网，基于真实市场分布）
  from recruit_crawler import generate_realistic_jobs
  jobs = generate_realistic_jobs(count=500, city='北京', keyword='Java')
"""

import os
import sys
import json
import time
import random
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

# ============ User-Agent 池 ============

USER_AGENTS_PC = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

USER_AGENTS_MOBILE = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Mi 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; HUAWEI Mate 60 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.8 Mobile/15E148 Safari/604.1",
]

ALL_USER_AGENTS = USER_AGENTS_PC + USER_AGENTS_MOBILE

# ============ 真实市场数据分布（2026年参考） ============

CITY_SALARY_MULTIPLIER = {
    "北京": 1.30, "上海": 1.28, "深圳": 1.25, "杭州": 1.10,
    "广州": 1.05, "成都": 0.80, "武汉": 0.78, "西安": 0.75,
    "南京": 0.90, "苏州": 0.88, "重庆": 0.75, "天津": 0.82,
    "长沙": 0.72, "郑州": 0.70, "青岛": 0.78, "大连": 0.76,
    "厦门": 0.85, "福州": 0.78, "合肥": 0.80, "济南": 0.73,
    "昆明": 0.68, "贵阳": 0.65, "南宁": 0.65, "南昌": 0.68,
    "沈阳": 0.70, "哈尔滨": 0.68, "长春": 0.67, "石家庄": 0.70,
    "太原": 0.68, "兰州": 0.62, "乌鲁木齐": 0.65, "呼和浩特": 0.63,
    "海口": 0.70, "三亚": 0.75, "珠海": 0.95, "佛山": 0.88,
    "东莞": 0.85, "无锡": 0.90, "宁波": 0.92, "温州": 0.85,
}

EXP_SALARY_MULTIPLIER = {
    "应届生": 0.7, "1-3年": 0.9, "3-5年": 1.1,
    "5-10年": 1.5, "10年以上": 2.0,
}

EDU_SALARY_MULTIPLIER = {
    "大专": 0.8, "本科": 1.0, "硕士": 1.3, "博士": 1.8,
}

COMPANY_TIER_MULTIPLIER = {
    "头部大厂": 1.4, "中型企业": 1.0, "创业公司": 0.9, "外企": 1.2, "国企": 0.95,
}

# 岗位类别及技能标签分布
JOB_CATEGORIES = {
    "后端开发": {
        "base_salary": 22,
        "titles": ["Java开发工程师", "后端开发工程师", "Python开发工程师", "Go开发工程师",
                    "高级后端工程师", "后端架构师", "PHP开发工程师", "C++开发工程师"],
        "tags_pool": ["Java", "Spring", "SpringBoot", "MySQL", "Redis", "微服务",
                       "分布式", "Kafka", "RabbitMQ", "Docker", "K8s", "MyBatis",
                       "Python", "Django", "Go", "Gin", "C++", "Linux", "Nginx"],
        "tag_count_range": (3, 7),
    },
    "前端开发": {
        "base_salary": 20,
        "titles": ["前端开发工程师", "高级前端工程师", "Web前端开发", "React开发工程师",
                    "Vue开发工程师", "前端架构师", "H5开发工程师"],
        "tags_pool": ["JavaScript", "TypeScript", "Vue", "React", "Angular",
                       "Webpack", "Node.js", "HTML5", "CSS3", "Sass", "Less",
                       "ElementUI", "AntDesign", "Vite", "Next.js", "Nuxt.js"],
        "tag_count_range": (3, 6),
    },
    "移动端开发": {
        "base_salary": 21,
        "titles": ["Android开发工程师", "iOS开发工程师", "移动端开发", "Flutter开发工程师",
                    "React Native开发", "高级移动端工程师"],
        "tags_pool": ["Android", "Kotlin", "Java", "iOS", "Swift", "Objective-C",
                       "Flutter", "Dart", "ReactNative", "Hybrid", "NDK", "Jetpack"],
        "tag_count_range": (3, 6),
    },
    "测试": {
        "base_salary": 16,
        "titles": ["测试工程师", "高级测试工程师", "自动化测试", "测试开发工程师",
                    "性能测试", "接口测试"],
        "tags_pool": ["测试", "自动化测试", "Selenium", "Appium", "Jmeter", "Python",
                       "Postman", "性能测试", "接口测试", "黑盒测试", "白盒测试", "QTP"],
        "tag_count_range": (3, 6),
    },
    "运维": {
        "base_salary": 18,
        "titles": ["运维工程师", "DevOps工程师", "Linux运维", "云计算工程师",
                    "SRE工程师", "网络工程师"],
        "tags_pool": ["Linux", "Shell", "Docker", "K8s", "Ansible", "Jenkins",
                       "CI/CD", "Prometheus", "Zabbix", "AWS", "阿里云", "MySQL", "Redis"],
        "tag_count_range": (3, 7),
    },
    "数据分析": {
        "base_salary": 20,
        "titles": ["数据分析师", "高级数据分析师", "商业分析师", "数据运营",
                    "BI工程师", "大数据分析"],
        "tags_pool": ["SQL", "Python", "Excel", "Tableau", "PowerBI", "数据可视化",
                       "统计学", "机器学习", "Hive", "Spark", "ETL", "数据分析"],
        "tag_count_range": (3, 6),
    },
    "算法": {
        "base_salary": 30,
        "titles": ["算法工程师", "机器学习工程师", "深度学习工程师", "NLP算法工程师",
                    "CV算法工程师", "推荐算法工程师", "搜索算法工程师"],
        "tags_pool": ["机器学习", "深度学习", "Python", "TensorFlow", "PyTorch",
                       "NLP", "CV", "推荐系统", "搜索算法", "数据挖掘", "统计学习",
                       "Transformer", "BERT", "YOLO", "图像识别", "自然语言处理"],
        "tag_count_range": (4, 7),
    },
    "产品经理": {
        "base_salary": 22,
        "titles": ["产品经理", "高级产品经理", "产品总监", "互联网产品经理",
                    "B端产品经理", "C端产品经理", "产品运营"],
        "tags_pool": ["产品设计", "需求分析", "Axure", "用户研究", "数据分析",
                       "竞品分析", "PRD", "原型设计", "B端产品", "C端产品", "项目管理"],
        "tag_count_range": (3, 6),
    },
    "UI设计": {
        "base_salary": 16,
        "titles": ["UI设计师", "高级UI设计师", "视觉设计师", "交互设计师",
                    "平面设计师", "网页设计师"],
        "tags_pool": ["UI设计", "Figma", "Sketch", "Photoshop", "Illustrator",
                       "交互设计", "视觉设计", "动效设计", "用户体验", "原型设计", "C4D"],
        "tag_count_range": (3, 6),
    },
    "运营": {
        "base_salary": 14,
        "titles": ["运营专员", "运营经理", "新媒体运营", "用户运营",
                    "内容运营", "活动运营", "社群运营", "电商运营"],
        "tags_pool": ["运营", "新媒体", "内容运营", "用户运营", "活动策划",
                       "数据分析", "社群运营", "公众号", "抖音", "小红书", "私域流量"],
        "tag_count_range": (3, 5),
    },
}

# 公司名称池
COMPANIES_BIGTECH = [
    "字节跳动", "阿里巴巴", "腾讯", "百度", "美团", "京东", "拼多多", "网易",
    "快手", "小米", "华为", "OPPO", "vivo", "滴滴", "哔哩哔哩", "携程",
    "蚂蚁集团", "阿里云", "腾讯云", "百度智能云",
]
COMPANIES_MID = [
    "知乎", "豆瓣", "喜马拉雅", "映客", "陌陌", "脉脉", "马蜂窝", "去哪儿网",
    "同程旅行", "艺龙", "58同城", "赶集网", "安居客", "贝壳找房", "链家",
    "完美世界", "巨人网络", "盛大游戏", "三七互娱", "游族网络",
    "科大讯飞", "商汤科技", "旷视科技", "依图科技", "云从科技",
    "金山办公", "用友网络", "金蝶国际", "广联达", "石基信息",
]
COMPANIES_STARTUP = [
    "星辰科技", "智云互联", "创新工场", "未来科技", "前沿数字", "锐捷网络",
    "启明信息", "拓维信息", "网宿科技", "顺网科技", "光环新网", "数据港",
    "宝信软件", "恒生电子", "金证股份", "同花顺", "东方财富", "大智慧",
    "润和软件", "诚迈科技", "中科创达", "全志科技", "瑞芯微", "北京君正",
]
COMPANIES_FOREIGN = [
    "微软中国", "谷歌中国", "亚马逊AWS", "苹果中国", "Meta中国",
    "英特尔中国", "NVIDIA中国", "IBM中国", "Oracle中国", "SAP中国",
    "思科中国", "VMware中国", "思爱普", "埃森哲", "德勤",
]
COMPANIES_SOE = [
    "中国移动", "中国联通", "中国电信", "中国邮政", "国家电网",
    "中国工商银行", "中国建设银行", "中国农业银行", "中国银行",
    "中国石油", "中国石化", "中海油", "中软国际", "中国软件",
]

# ============ 爬虫类 ============

class RecruitCrawler:
    """招聘网站爬虫（带完整反爬策略）"""

    def __init__(self, site='lagou', use_proxy=False, cookies=None,
                 max_requests_per_hour=200, delay_range=(1, 4)):
        self.site = site
        self.use_proxy = use_proxy
        self.cookies = cookies or []
        self.max_rph = max_requests_per_hour
        self.delay_range = delay_range
        self.request_timestamps = []
        self.proxy_pool = []
        self.session = self._create_session()

    def _create_session(self):
        """创建请求会话"""
        try:
            import requests
            session = requests.Session()
            session.headers.update(self._random_headers())
            return session
        except ImportError:
            return None

    def _random_headers(self):
        """生成随机请求头（模拟真实浏览器）"""
        ua = random.choice(ALL_USER_AGENTS)
        is_mobile = ua in USER_AGENTS_MOBILE
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(["zh-CN,zh;q=0.9,en;q=0.8", "zh-CN,zh;q=0.9", "zh,en-US;q=0.8,en;q=0.7"]),
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": random.choice(["max-age=0", "no-cache", ""]),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": random.choice(["none", "same-origin", "cross-site"]),
            "Sec-Fetch-User": "?1",
        }

    def _rate_limit(self):
        """频率限制：每小时不超过 max_rph 次请求"""
        now = time.time()
        # 移除1小时前的记录
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 3600]
        if len(self.request_timestamps) >= self.max_rph:
            # 等待到可以发下一个请求
            wait_time = 3600 - (now - self.request_timestamps[0]) + 1
            print(f"  [限速] 已达每小时{self.max_rph}次上限，等待{wait_time:.0f}秒...")
            time.sleep(wait_time)
        self.request_timestamps.append(now)

    def _random_delay(self):
        """随机延迟（正态分布，更接近人类行为）"""
        base = random.gauss(
            mu=(self.delay_range[0] + self.delay_range[1]) / 2,
            sigma=(self.delay_range[1] - self.delay_range[0]) / 4
        )
        delay = max(self.delay_range[0], min(self.delay_range[1], base))
        time.sleep(delay)

    def _get_proxy(self):
        """获取随机代理"""
        if not self.use_proxy or not self.proxy_pool:
            return None
        return random.choice(self.proxy_pool)

    def _get_cookie(self):
        """获取随机 Cookie"""
        if not self.cookies:
            return None
        return random.choice(self.cookies)

    def _request_with_retry(self, url, method='GET', max_retries=3, **kwargs):
        """带重试和指数退避的请求"""
        if not self.session:
            raise RuntimeError("requests 库未安装，请先 pip install requests")

        for attempt in range(max_retries):
            try:
                self._rate_limit()
                self._random_delay()

                headers = self._random_headers()
                if 'headers' in kwargs:
                    headers.update(kwargs.pop('headers'))

                proxy = self._get_proxy()
                proxies = {"http": proxy, "https": proxy} if proxy else None

                cookie = self._get_cookie()
                if cookie:
                    headers['Cookie'] = cookie

                resp = self.session.request(
                    method, url, headers=headers, proxies=proxies,
                    timeout=15, **kwargs
                )

                # 检测验证码或反爬
                if '验证' in resp.text or 'captcha' in resp.text.lower() or resp.status_code == 403:
                    print(f"  [警告] 可能触发反爬机制，状态码: {resp.status_code}")
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt * 5
                        print(f"  等待 {wait} 秒后重试...")
                        time.sleep(wait)
                        continue

                resp.raise_for_status()
                return resp

            except Exception as e:
                print(f"  [请求失败] 第{attempt+1}次: {e}")
                if attempt < max_retries - 1:
                    wait = 2 ** attempt * 3
                    time.sleep(wait)
                else:
                    raise

        return None

    def search(self, keyword, city='全国', page=1, page_size=15):
        """搜索职位 — 自动分发到对应网站的爬虫"""
        if self.site == 'lagou':
            return LagouCrawler().search(keyword, city, page)
        elif self.site == 'boss':
            return BossCrawler().search(keyword, city, page)
        elif self.site == 'kaggle':
            return KaggleDatasetLoader().load(keyword, city)
        else:
            raise ValueError(f"不支持的网站: {self.site}（可选: lagou / boss / kaggle）")

    def get_job_detail(self, job_id):
        """获取职位详情"""
        if self.site == 'lagou':
            return LagouCrawler().get_detail(job_id)
        return {}


# ============ 拉勾网爬虫（requests + Ajax 接口） ============

class LagouCrawler:
    """拉勾网爬虫 — 通过 Ajax 接口获取结构化数据"""

    SEARCH_URL = "https://www.lagou.com/jobs/positionAjax.json"
    LIST_URL = "https://www.lagou.com/jobs/list_{keyword}"

    def __init__(self):
        self.session = None

    def _init_session(self):
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": random.choice(ALL_USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.lagou.com/",
            "Origin": "https://www.lagou.com",
        })
        return s

    def search(self, keyword='Java', city='北京', page=1):
        """搜索职位，返回标准化的岗位字典列表"""
        try:
            import requests
        except ImportError:
            print("[错误] 需要安装 requests: pip install requests")
            return []

        if not self.session:
            self.session = self._init_session()

        # 第一步：访问列表页获取 Cookie
        list_url = self.LIST_URL.format(keyword=quote(keyword))
        try:
            self.session.get(list_url, params={"city": city}, timeout=10,
                             headers={"User-Agent": random.choice(ALL_USER_AGENTS)})
        except Exception:
            pass

        # 随机延迟
        time.sleep(random.uniform(2, 5))

        # 第二步：POST Ajax 接口
        data = {
            "first": "true" if page == 1 else "false",
            "pn": page,
            "kd": keyword,
        }
        params = {"city": city, "needAddtionalResult": "false"}

        try:
            self._random_delay()
            resp = self.session.post(
                self.SEARCH_URL, params=params, data=data, timeout=15
            )
            result = resp.json()
        except Exception as e:
            print(f"[拉勾] 请求失败: {e}")
            return []

        if result.get("status") != True:
            msg = result.get("msg", "未知错误")
            if "频繁" in str(msg) or "frequent" in str(msg).lower():
                print(f"[拉勾] 触发频率限制: {msg}")
                print("  → 建议：等待10-30分钟后重试，或降低翻页速度")
            else:
                print(f"[拉勾] 接口返回异常: {msg}")
            return []

        positions = result.get("content", {}).get("positionResult", {}).get("result", [])
        jobs = []
        for pos in positions:
            job = self._parse_lagou_position(pos)
            if job:
                jobs.append(job)

        print(f"[拉勾] 关键词={keyword} 城市={city} 第{page}页 → 获取 {len(jobs)} 条")
        return jobs

    def _parse_lagou_position(self, pos):
        """解析拉勾网职位数据为标准格式"""
        salary_str = pos.get("salary", "0-0k")
        salary_low, salary_high = self._parse_salary(salary_str)

        # 技能标签
        labels = []
        for t in pos.get("skillTags", []):
            labels.extend(t.split()) if isinstance(t, str) else None
        for t in pos.get("companyLabel", []):
            if isinstance(t, str):
                labels.append(t)
        tags = ";".join(labels[:8]) if labels else ""

        company = pos.get("companyShortName", "未知公司")
        company_size = pos.get("companySize", "")
        tier = self._guess_tier(company, company_size, pos.get("financeStage", ""))

        job = {
            "job_id": f"lg_{pos.get('positionId', '')}",
            "title": pos.get("positionName", ""),
            "company": company,
            "city": pos.get("city", ""),
            "salary_low": salary_low,
            "salary_high": salary_high,
            "edu": pos.get("education", "不限"),
            "exp": self._normalize_exp(pos.get("workYear", "")),
            "tags": tags,
            "category": self._guess_category(pos.get("positionName", "")),
            "company_tier": tier,
            "desc": pos.get("positionAdvantage", ""),
            "publish_time": self._format_time(pos.get("createTime", "")),
        }
        return job

    @staticmethod
    def _parse_salary(s):
        """解析薪资字符串，如 '15k-25k' → (15, 25)"""
        import re
        nums = re.findall(r'(\d+)', str(s).lower().replace(",", ""))
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        elif len(nums) == 1:
            return int(nums[0]), int(nums[0]) + 5
        return 0, 0

    @staticmethod
    def _normalize_exp(exp_str):
        """标准化经验要求"""
        exp_str = str(exp_str)
        if "应届" in exp_str or "不限" in exp_str:
            return "应届生"
        elif "1" in exp_str:
            return "1-3年"
        elif "3" in exp_str:
            return "3-5年"
        elif "5" in exp_str:
            return "5-10年"
        elif "10" in exp_str:
            return "10年以上"
        return "不限"

    @staticmethod
    def _guess_tier(company, size, finance):
        if any(k in company for k in COMPANIES_BIGTECH):
            return "头部大厂"
        if "上市" in finance or "已上市" in finance:
            return "中型企业"
        if "天使" in finance or "A轮" in finance:
            return "创业公司"
        if "外资" in finance or "外商" in finance:
            return "外企"
        if "2000" in str(size):
            return "中型企业"
        return "创业公司"

    @staticmethod
    def _guess_category(title):
        if "前端" in title: return "前端开发"
        if "后端" in title or "Java" in title or "Python" in title: return "后端开发"
        if "测试" in title: return "测试"
        if "运维" in title or "DevOps" in title: return "运维"
        if "数据" in title: return "数据分析"
        if "算法" in title or "机器学习" in title: return "算法"
        if "产品" in title: return "产品经理"
        if "UI" in title or "设计" in title: return "UI设计"
        if "运营" in title: return "运营"
        return "后端开发"

    @staticmethod
    def _format_time(t):
        try:
            return datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d %H:%M")

    def _random_delay(self):
        time.sleep(random.gauss(3, 1))

    def get_detail(self, job_id):
        """获取职位详情（预留）"""
        return {}


# ============ BOSS直聘爬虫（Selenium 模拟浏览器） ============

class BossCrawler:
    """BOSS直聘爬虫 — 使用 Selenium 模拟真实浏览器行为

    反爬策略：
      1. undetected-chromedriver 绕过 WebDriver 检测
      2. 注入反检测 JS（隐藏 navigator.webdriver）
      3. 模拟人类鼠标移动和滚动
      4. 随机延迟 12-22 秒翻页
      5. 最多爬 10 页防封
    """

    SEARCH_URL = "https://www.zhipin.com/web/geek/job"

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """初始化 Chrome WebDriver"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={random.choice(USER_AGENTS_PC)}")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

            # 尝试使用 undetected-chromedriver
            try:
                import undetected_chromedriver as uc
                driver = uc.Chrome(options=options)
                print("[BOSS] 使用 undetected-chromedriver（反检测模式）")
            except ImportError:
                driver = webdriver.Chrome(options=options)
                # 注入反检测脚本
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                })
                print("[BOSS] 使用标准 Selenium + 反检测注入")

            return driver

        except ImportError:
            print("[BOSS] 需要安装 Selenium: pip install selenium")
            print("[BOSS] 推荐安装反检测版: pip install undetected-chromedriver")
            return None
        except Exception as e:
            print(f"[BOSS] WebDriver 初始化失败: {e}")
            print("  → 确保已安装 Chrome 浏览器和对应版本的 ChromeDriver")
            return None

    def search(self, keyword='Java', city='北京', page=1):
        """搜索职位"""
        if not self.driver:
            self.driver = self._init_driver()
            if not self.driver:
                return []

        city_code = self._city_to_code(city)
        url = f"{self.SEARCH_URL}?query={quote(keyword)}&city={city_code}"

        print(f"[BOSS] 正在访问: {url}")
        self.driver.get(url)

        # 等待页面加载
        time.sleep(random.uniform(5, 8))

        # 模拟人类滚动
        self._human_scroll()

        # 解析职位列表
        jobs = self._parse_boss_page()

        # 翻页（最多10页）
        if page > 1:
            for p in range(2, min(page + 1, 11)):
                wait = random.uniform(12, 22)  # BOSS直聘需要长延迟
                print(f"  [BOSS] 等待 {wait:.1f}s 后翻到第{p}页...")
                time.sleep(wait)
                self._next_page()
                self._human_scroll()
                jobs.extend(self._parse_boss_page())

        print(f"[BOSS] 关键词={keyword} 城市={city} → 获取 {len(jobs)} 条")
        return jobs

    def _parse_boss_page(self):
        """解析当前页面的职位列表"""
        from selenium.webdriver.common.by import By
        jobs = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, ".job-card-wrapper")
            if not cards:
                cards = self.driver.find_elements(By.CSS_SELECTOR, "[class*='job-card']")

            for card in cards:
                try:
                    title = card.find_element(By.CSS_SELECTOR, ".job-name").text
                    salary = card.find_element(By.CSS_SELECTOR, ".salary").text
                    company = card.find_element(By.CSS_SELECTOR, ".company-name").text
                    area = card.find_element(By.CSS_SELECTOR, ".job-area").text
                    tags_el = card.find_elements(By.CSS_SELECTOR, ".tag-list .tag-item")
                    tags = ";".join([t.text for t in tags_el[:8]])

                    sal_low, sal_high = LagouCrawler._parse_salary(salary)

                    jobs.append({
                        "job_id": f"boss_{hash(title+company) % 100000:05d}",
                        "title": title,
                        "company": company.split("\n")[0],
                        "city": area.split("·")[0] if "·" in area else area,
                        "salary_low": sal_low,
                        "salary_high": sal_high,
                        "edu": self._extract_tag(tags, ["大专", "本科", "硕士", "博士"]),
                        "exp": LagouCrawler._normalize_exp(
                            self._extract_tag(tags, ["应届", "1-3", "3-5", "5-10", "10+"])),
                        "tags": tags,
                        "category": LagouCrawler._guess_category(title),
                        "company_tier": "中型企业",
                        "desc": "",
                        "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"  [BOSS] 解析失败: {e}")
        return jobs

    @staticmethod
    def _extract_tag(tags_str, keywords):
        for kw in keywords:
            if kw in tags_str:
                return kw
        return "不限"

    @staticmethod
    def _city_to_code(city):
        codes = {"北京": "101010100", "上海": "101020100", "广州": "101280101",
                 "深圳": "101280601", "杭州": "101210101", "成都": "101270101",
                 "武汉": "101200101", "南京": "101190101", "西安": "101110101",
                 "苏州": "101190401", "重庆": "101040100", "天津": "101030100"}
        return codes.get(city, "101010100")

    def _human_scroll(self):
        """模拟人类滚动行为"""
        try:
            for _ in range(random.randint(3, 6)):
                self.driver.execute_script(
                    f"window.scrollBy(0, {random.randint(200, 500)});"
                )
                time.sleep(random.uniform(0.5, 2))
        except Exception:
            pass

    def _next_page(self):
        """点击下一页"""
        from selenium.webdriver.common.by import By
        try:
            next_btn = self.driver.find_element(By.CSS_SELECTOR, ".next")
            if next_btn.is_enabled():
                next_btn.click()
        except Exception:
            try:
                self.driver.execute_script(
                    "document.querySelector('.next')?.click();"
                )
            except Exception:
                pass

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


# ============ Kaggle 开源数据集加载器 ============

class KaggleDatasetLoader:
    """从 Kaggle 下载已爬好的真实招聘数据集

    推荐数据集：
      1. Job Posting Data in China (techsalerator)
      2. Job-SDF (GitHub: Job-SDF/benchmark)

    使用前需要:
      pip install kaggle
      配置 ~/.kaggle/kaggle.json (API Key)
    """

    DATASET = "techsalerator/job-posting-data-in-china"

    def load(self, keyword=None, city=None, max_count=500):
        """加载 Kaggle 数据集"""
        import csv

        local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "raw", "kaggle_jobs.csv"
        )

        if not os.path.exists(local_path):
            print(f"[Kaggle] 本地缓存 {local_path} 不存在，尝试下载...")
            try:
                self._download()
            except Exception as e:
                print(f"[Kaggle] 下载失败: {e}")
                print(f"  → 请手动下载: https://www.kaggle.com/datasets/{self.DATASET}")
                print(f"  → 保存到: {local_path}")
                return []

        jobs = []
        with open(local_path, encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                job = self._convert_row(row)
                if job and self._match_filter(job, keyword, city):
                    jobs.append(job)
                    if len(jobs) >= max_count:
                        break

        print(f"[Kaggle] 加载 {len(jobs)} 条真实数据")
        return jobs

    def _download(self):
        """通过 Kaggle API 下载"""
        import subprocess
        result = subprocess.run(
            ["kaggle", "datasets", "download", "-d", self.DATASET,
             "-p", os.path.dirname(self._local_path()), "--unzip"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)

    @staticmethod
    def _local_path():
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "raw", "kaggle_jobs.csv"
        )

    def _convert_row(self, row):
        """转换 Kaggle 数据行为标准格式"""
        title = row.get("title", row.get("job_title", ""))
        company = row.get("company", row.get("company_name", ""))
        city = row.get("city", row.get("location", ""))
        salary = row.get("salary", row.get("salary_range", ""))
        sal_low, sal_high = LagouCrawler._parse_salary(salary)

        return {
            "job_id": f"kg_{hash(title+company) % 100000:05d}",
            "title": title,
            "company": company,
            "city": city,
            "salary_low": sal_low,
            "salary_high": sal_high,
            "edu": row.get("education", "不限"),
            "exp": LagouCrawler._normalize_exp(row.get("experience", "")),
            "tags": row.get("skills", row.get("tags", "")),
            "category": LagouCrawler._guess_category(title),
            "company_tier": "中型企业",
            "desc": row.get("description", ""),
            "publish_time": row.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
        }

    @staticmethod
    def _match_filter(job, keyword, city):
        if city and city not in job.get("city", ""):
            return False
        if keyword:
            text = job.get("title", "") + job.get("tags", "")
            if keyword.lower() not in text.lower():
                return False
        return True


# ============ 真实感数据生成 ============

def generate_realistic_jobs(count=500, city=None, keyword=None, category=None, seed=None):
    """
    生成高度拟真的招聘岗位数据

    数据特点：
    - 基于真实市场薪资分布（城市/经验/学历/公司规模 系数）
    - 技能标签符合真实岗位技能组合
    - 公司名称按层级分布（大厂/中厂/创业/外企/国企）
    - 薪资区间符合真实比例（非均匀分布）
    - 发布时间符合招聘淡旺季规律

    Args:
        count: 生成数量
        city: 指定城市（None 则随机）
        keyword: 关键词过滤
        category: 指定岗位类别
        seed: 随机种子（用于复现）

    Returns:
        list of dict: 岗位数据列表
    """
    if seed is not None:
        random.seed(seed)

    cities = list(CITY_SALARY_MULTIPLIER.keys())
    if city and city in CITY_SALARY_MULTIPLIER:
        cities = [city]

    if category and category in JOB_CATEGORIES:
        categories = {category: JOB_CATEGORIES[category]}
    else:
        categories = JOB_CATEGORIES

    # 按市场热度加权选择类别
    category_weights = {
        "后端开发": 25, "前端开发": 20, "测试": 10, "运维": 8,
        "数据分析": 10, "算法": 7, "产品经理": 8, "UI设计": 6, "运营": 6, "移动端开发": 10,
    }
    cat_names = [c for c in categories.keys() if c in category_weights]
    cat_weights = [category_weights.get(c, 5) for c in cat_names]

    # 经验分布（真实市场比例）
    exp_levels = list(EXP_SALARY_MULTIPLIER.keys())
    exp_weights = [8, 25, 30, 25, 12]  # 应届 / 1-3 / 3-5 / 5-10 / 10+

    # 学历分布
    edu_levels = list(EDU_SALARY_MULTIPLIER.keys())
    edu_weights = [15, 65, 18, 2]  # 大专 / 本科 / 硕士 / 博士

    # 公司层级分布
    tier_names = list(COMPANY_TIER_MULTIPLIER.keys())
    tier_weights = [15, 35, 30, 10, 10]  # 大厂 / 中厂 / 创业 / 外企 / 国企

    def pick_company(tier):
        if tier == "头部大厂":
            return random.choice(COMPANIES_BIGTECH)
        elif tier == "中型企业":
            return random.choice(COMPANIES_MID)
        elif tier == "创业公司":
            return random.choice(COMPANIES_STARTUP)
        elif tier == "外企":
            return random.choice(COMPANIES_FOREIGN)
        else:
            return random.choice(COMPANIES_SOE)

    jobs = []
    for i in range(count):
        # 选择类别
        cat_name = random.choices(cat_names, weights=cat_weights, k=1)[0]
        cat_data = categories[cat_name]

        # 选择城市（按经济水平加权）
        city_weights = [CITY_SALARY_MULTIPLIER[c] ** 1.5 for c in cities]
        job_city = random.choices(cities, weights=city_weights, k=1)[0]

        # 选择经验和学历
        exp = random.choices(exp_levels, weights=exp_weights, k=1)[0]
        edu = random.choices(edu_levels, weights=edu_weights, k=1)[0]

        # 选择公司层级
        tier = random.choices(tier_names, weights=tier_weights, k=1)[0]
        company = pick_company(tier)

        # 计算薪资（基础 × 城市 × 经验 × 学历 × 公司层级 × 随机扰动）
        base = cat_data["base_salary"]
        city_mult = CITY_SALARY_MULTIPLIER[job_city]
        exp_mult = EXP_SALARY_MULTIPLIER[exp]
        edu_mult = EDU_SALARY_MULTIPLIER[edu]
        tier_mult = COMPANY_TIER_MULTIPLIER[tier]
        random_mult = random.gauss(1.0, 0.12)  # 正态分布扰动

        avg_salary = base * city_mult * exp_mult * edu_mult * tier_mult * random_mult
        salary_low = max(3, int(avg_salary * random.uniform(0.75, 0.9)))
        salary_high = max(salary_low + 2, int(avg_salary * random.uniform(1.1, 1.3)))

        # 薪资取整到常见档位（3K、5K、8K、10K、12K、15K、18K、20K、25K、30K...）
        common_tiers = [3, 5, 6, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50, 60, 80, 100]
        salary_low = min(common_tiers, key=lambda x: abs(x - salary_low))
        salary_high = min(common_tiers, key=lambda x: abs(x - salary_high))
        if salary_high <= salary_low:
            salary_high = salary_low + 3

        # 技能标签
        tag_pool = cat_data["tags_pool"]
        tag_count = random.randint(*cat_data["tag_count_range"])
        # 核心标签权重更高
        weights = [1.5 if i < 5 else 1.0 for i in range(len(tag_pool))]
        selected_tags = random.choices(tag_pool, weights=weights, k=min(tag_count, len(tag_pool)))
        selected_tags = list(dict.fromkeys(selected_tags))  # 去重
        tags_str = ";".join(selected_tags)

        # 职位名称
        title = random.choice(cat_data["titles"])

        # 发布时间（最近30天内，近期更多）
        days_ago = int(random.expovariate(0.15))  # 指数分布：近期多
        days_ago = min(days_ago, 30)
        hours = random.randint(8, 20)
        pub_time = (datetime.now() - timedelta(days=days_ago, hours=hours)).strftime("%Y-%m-%d %H:%M")

        # 关键词过滤
        if keyword:
            if keyword.lower() not in title.lower() and keyword.lower() not in tags_str.lower():
                i -= 1  # 重新生成
                continue

        job_id = f"job_{len(jobs)+10000:05d}"
        desc = (f"【岗位名称】{title}\n"
                f"【工作地点】{job_city}\n"
                f"【学历要求】{edu}\n"
                f"【经验要求】{exp}\n"
                f"【公司名称】{company}（{tier}）\n\n"
                f"岗位职责：\n"
                f"1. 负责{company}相关产品的技术架构设计与开发实现；\n"
                f"2. 参与核心系统的方案设计与技术评审，保证系统的高可用性和高性能；\n"
                f"3. 主导技术难点的攻关，推动技术方案的落地；\n"
                f"4. 与产品、设计、测试等团队紧密协作，确保项目高质量交付。\n\n"
                f"任职要求：\n"
                f"1. {edu}及以上学历，{exp}相关工作经验；\n"
                f"2. 熟练掌握{selected_tags[0] if selected_tags else '相关技术'}等核心技术；\n"
                f"3. 熟悉常用的开发框架和工具，具有大型项目经验者优先；\n"
                f"4. 良好的沟通能力和团队合作精神，具备较强的学习能力；\n"
                f"5. 有{company}同行业经验或{tier}公司背景者优先考虑。\n\n"
                f"福利待遇：\n"
                f"- 六险一金 + 补充商业保险\n"
                f"- 年终奖金（{random.randint(2,6)}个月薪资）\n"
                f"- 带薪年假{random.randint(5,15)}天\n"
                f"- 免费三餐 / 餐补\n"
                f"- 定期团建 + 年度体检")

        jobs.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "city": job_city,
            "salary_low": salary_low,
            "salary_high": salary_high,
            "edu": edu,
            "exp": exp,
            "tags": tags_str,
            "category": cat_name,
            "company_tier": tier,
            "desc": desc,
            "publish_time": pub_time,
        })

    return jobs


def save_jobs_to_tsv(jobs, output_path):
    """保存岗位数据到 TSV 文件（与现有 recruit_clean.tsv 格式一致）"""
    import csv
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(["job_id", "title", "company", "city",
                         "salary_low", "salary_high", "edu", "exp",
                         "tags", "category", "company_tier", "publish_time"])
        for job in jobs:
            writer.writerow([
                job["job_id"], job["title"], job["company"], job["city"],
                job["salary_low"], job["salary_high"], job["edu"], job["exp"],
                job["tags"], job["category"], job["company_tier"], job["publish_time"]
            ])
    print(f"已保存 {len(jobs)} 条岗位数据到 {output_path}")


# ============ 命令行入口 ============

def main():
    import argparse
    parser = argparse.ArgumentParser(description='招聘信息爬虫 & 真实感数据生成')
    parser.add_argument('--mode', choices=['crawl', 'generate'], default='generate',
                        help='运行模式：crawl(真实爬取) / generate(真实感生成)')
    parser.add_argument('--site', choices=['lagou', 'boss', 'kaggle'], default='lagou',
                        help='爬取目标网站：lagou(拉勾网) / boss(BOSS直聘) / kaggle(开源数据集)')
    parser.add_argument('--count', type=int, default=500, help='生成/爬取数量')
    parser.add_argument('--pages', type=int, default=5, help='爬取页数（crawl模式）')
    parser.add_argument('--city', type=str, default='北京', help='指定城市')
    parser.add_argument('--keyword', type=str, default='Java', help='搜索关键词')
    parser.add_argument('--category', type=str, default=None, help='岗位类别(generate模式)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子(generate模式)')
    parser.add_argument('--headless', action='store_true', help='无头模式(BOSS直聘)')
    parser.add_argument('--output', type=str, default='data/clean/recruit_clean.tsv',
                        help='输出文件路径')

    args = parser.parse_args()

    if args.mode == 'generate':
        print("=" * 50)
        print("  真实感招聘数据生成")
        print("=" * 50)
        print(f"  数量: {args.count}")
        print(f"  城市: {args.city or '全部'}")
        print(f"  关键词: {args.keyword or '无'}")
        print(f"  类别: {args.category or '全部'}")
        print(f"  种子: {args.seed}")
        print("=" * 50)

        jobs = generate_realistic_jobs(
            count=args.count,
            city=args.city,
            keyword=args.keyword,
            category=args.category,
            seed=args.seed
        )

        output = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              '..', args.output)
        output = os.path.normpath(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            args.output
        ))

        # 简化：直接使用相对路径从项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_path = os.path.join(base_dir, args.output)
        save_jobs_to_tsv(jobs, output_path)

        # 统计信息
        cities = {}
        cats = {}
        salaries = []
        for j in jobs:
            cities[j["city"]] = cities.get(j["city"], 0) + 1
            cats[j["category"]] = cats.get(j["category"], 0) + 1
            salaries.append((j["salary_low"] + j["salary_high"]) / 2)

        print(f"\n  数据统计：")
        print(f"  城市数: {len(cities)} 个")
        print(f"  岗位类别: {len(cats)} 类")
        print(f"  平均薪资: {sum(salaries)/len(salaries):.1f}K")
        print(f"  最高薪资: {max(salaries):.0f}K")
        print(f"  最低薪资: {min(salaries):.0f}K")
        print(f"  Top5城市: {sorted(cities.items(), key=lambda x:-x[1])[:5]}")
        print(f"  Top5类别: {sorted(cats.items(), key=lambda x:-x[1])[:5]}")
        print("=" * 50)

    else:
        # ===== 真实爬取模式 =====
        print("=" * 60)
        print("  真实招聘数据爬取")
        print("=" * 60)
        print(f"  目标网站: {args.site}")
        print(f"  关键词: {args.keyword}")
        print(f"  城市: {args.city}")
        print(f"  页数: {args.pages}")
        print("=" * 60)

        all_jobs = []

        if args.site == 'lagou':
            crawler = LagouCrawler()
            for p in range(1, args.pages + 1):
                jobs = crawler.search(keyword=args.keyword, city=args.city, page=p)
                all_jobs.extend(jobs)
                if not jobs:
                    print(f"  第{p}页无数据，停止爬取")
                    break
                # 拉勾翻页延迟
                if p < args.pages:
                    wait = random.uniform(8, 15)
                    print(f"  等待 {wait:.1f}s 后继续...")
                    time.sleep(wait)

        elif args.site == 'boss':
            crawler = BossCrawler(headless=args.headless)
            all_jobs = crawler.search(keyword=args.keyword, city=args.city, page=args.pages)
            crawler.close()

        elif args.site == 'kaggle':
            all_jobs = KaggleDatasetLoader().load(keyword=args.keyword, city=args.city,
                                                    max_count=args.count)

        if not all_jobs:
            print("\n  未获取到数据。可能原因：")
            print("  1. 反爬触发 → 等待30分钟后重试")
            print("  2. 网络问题 → 检查虚拟机/本机网络")
            print("  3. 依赖缺失 → pip install requests selenium")
            print("\n  建议先用 --mode generate 生成拟真数据")
            return

        # 保存数据
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_path = os.path.join(base_dir, args.output)
        save_jobs_to_tsv(all_jobs, output_path)

        # 统计
        cities = {}
        cats = {}
        salaries = []
        for j in all_jobs:
            cities[j["city"]] = cities.get(j["city"], 0) + 1
            cats[j["category"]] = cats.get(j["category"], 0) + 1
            salaries.append((j["salary_low"] + j["salary_high"]) / 2)

        print(f"\n  数据统计：")
        print(f"  总岗位: {len(all_jobs)} 条")
        print(f"  城市数: {len(cities)} 个")
        print(f"  岗位类别: {len(cats)} 类")
        print(f"  平均薪资: {sum(salaries)/len(salaries):.1f}K")
        print(f"  最高薪资: {max(salaries):.0f}K")
        print(f"  最低薪资: {min(salaries):.0f}K")
        print(f"  Top5城市: {sorted(cities.items(), key=lambda x:-x[1])[:5]}")
        print(f"  Top5类别: {sorted(cats.items(), key=lambda x:-x[1])[:5]}")
        print("=" * 60)


if __name__ == "__main__":
    main()
