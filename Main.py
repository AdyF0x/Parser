import asyncio
import aiohttp
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from GPT import GPTProcessor

class HabrParser:
    """Парсер Habr через RSS + веб"""
    
    def __init__(self):
        self.base_url = "https://habr.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = None
        
        # RSS ленты
        self.rss_feeds = [
            "https://habr.com/ru/rss/all/",
            "https://habr.com/ru/rss/interesting/",
        ]
        
    async def search(self, query: str = None, limit: int = 20) -> List[Dict]:
        print(f"🔍 Поиск: '{query}'")
        all_articles = []
        seen_urls = set()
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            
            print("\n📡 RSS парсер...")
            for feed_url in self.rss_feeds:
                try:
                    articles = await self._fetch_rss(feed_url)
                    for article in articles:
                        url = article.get('url')
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_articles.append(article)
                    print(f"  ✅ {feed_url.split('/')[-2]}: {len(articles)} статей")
                except Exception as e:
                    print(f"  ❌ Ошибка: {e}")
                    
            if query:
                all_articles = self._filter_by_query(all_articles, query)
                print(f"\n🔍 После фильтрации по '{query}': {len(all_articles)} статей")
            
            if all_articles:
                print(f"\n📖 Парсинг {min(len(all_articles), limit)} статей...")
                for i, article in enumerate(all_articles[:limit]):
                    print(f"  {i+1}. {article.get('title', '')[:50]}...")
                    
                    full_content = await self._get_full_article(article.get('url'))
                    if full_content:
                        article.update(full_content)
            
            return all_articles[:limit]
    
    async def _fetch_rss(self, feed_url: str) -> List[Dict]:
        articles = []
        
        try:
            async with self.session.get(feed_url, headers=self.headers, timeout=15) as response:
                if response.status == 200:
                    content = await response.text()
                    articles = self._parse_rss(content)
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            
        return articles
    
    def _parse_rss(self, content: str) -> List[Dict]:
        articles = []
        
        try:
            root = ET.fromstring(content)
            for item in root.findall('.//item'):
                article = self._parse_rss_item(item)
                if article.get('url') and article.get('title'):
                    articles.append(article)
                    
        except ET.ParseError:
            soup = BeautifulSoup(content, 'html.parser')
            for item in soup.find_all('item'):
                article = self._parse_rss_item_soup(item)
                if article.get('url') and article.get('title'):
                    articles.append(article)
        
        return articles
    
    def _parse_rss_item(self, item) -> Dict:
        article = {}
        
        title = item.find('title')
        if title is not None:
            article['title'] = title.text
        
        link = item.find('link')
        if link is not None:
            article['url'] = link.text
        
        desc = item.find('description')
        if desc is not None and desc.text:
            article['description'] = BeautifulSoup(desc.text, 'html.parser').get_text()[:500]
        
        pub = item.find('pubDate')
        if pub is not None:
            article['date'] = pub.text
        
        author = item.find('author')
        if author is not None:
            article['author'] = author.text
        
        tags = []
        for tag in item.findall('category'):
            if tag.text:
                tags.append(tag.text)
        if tags:
            article['tags'] = tags
        
        return article
    
    def _parse_rss_item_soup(self, item) -> Dict:
        article = {}
        
        title = item.find('title')
        if title:
            article['title'] = title.get_text()
        
        link = item.find('link')
        if link:
            article['url'] = link.get_text()
        
        desc = item.find('description')
        if desc:
            article['description'] = BeautifulSoup(desc.get_text(), 'html.parser').get_text()[:500]
        
        return article
    
    def _filter_by_query(self, articles: List[Dict], query: str) -> List[Dict]:
        query_words = query.lower().split()
        filtered = []
        
        for article in articles:
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            if all(word in text for word in query_words):
                filtered.append(article)
        
        return filtered
    
    async def _get_full_article(self, url: str) -> Dict:
        result = {}
        
        try:
            async with self.session.get(url, headers=self.headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content = self._extract_content(soup)
                    result['content'] = content
                    result['content_length'] = len(content)
                    
                    hubs = []
                    for hub in soup.select('a.hub, a.post__hub'):
                        hub_text = hub.get_text().strip()
                        if hub_text:
                            hubs.append(hub_text)
                    if hubs:
                        result['hubs'] = hubs
                    
        except Exception as e:
            pass
            
        return result
    
    def _extract_content(self, soup) -> str:
        content = ""
        
        for selector in ['div.post__text', 'div.article__body', 'div.content']:
            for elem in soup.select(selector):
                text = elem.get_text(separator=' ', strip=True)
                if text and len(text) > 100:
                    content += text + " "
        
        if not content or len(content) < 100:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    content += text + " "
        
        return ' '.join(content.split())[:5000]


class ArticleFilter:
    
    def __init__(self):
        self.advert_keywords = [
            'скидка', 'промокод', 'купить', 'заказать', 'цена',
            'реклама', 'партнер', 'спецпредложение', 'акция', 'бонус',
            'оплата', 'стоимость', 'каталог'
        ]
    
    def remove_advertorial(self, articles: List[Dict], threshold: int = 2) -> List[Dict]:
        filtered = []
        
        for article in articles:
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            advert_count = sum(1 for kw in self.advert_keywords if kw in text)
            
            if advert_count < threshold:
                filtered.append(article)
        
        return filtered
    
    def filter_by_length(self, articles: List[Dict], min_length: int = 100) -> List[Dict]:
        filtered = []
        
        for article in articles:
            content = article.get('content', '')
            if len(content) >= min_length:
                filtered.append(article)
        
        return filtered

class HabrApp:
    
    def __init__(self):
        self.parser = HabrParser()
        self.filter = ArticleFilter()
        self.gpt = None
        self.articles = []
        
    def init_gpt(self, api_key: str) -> bool:
        try:
            self.gpt = GPTProcessor(api_key)
            print("✅ GPT-5.5 инициализирован")
            return True
        except Exception as e:
            print(f"❌ Ошибка GPT: {e}")
            return False
    
    async def search(self, query: str, limit: int = 20, use_gpt: bool = False) -> List[Dict]:
#    query: Поисковый запрос
#    limit: Максимальное количество
#   use_gpt: Использовать GPT для фильтрации

        print("\n" + "=" * 70)
        print(f"🚀 ПОИСК: '{query}' (лимит: {limit})")
        print("=" * 70)
        
        print("\n📡 Шаг 1: Парсинг Habr...")
        self.articles = await self.parser.search(query, limit * 2)
        
        if not self.articles:
            print("❌ Статьи не найдены")
            return []
        
        print(f"\n📊 Найдено: {len(self.articles)} статей")
        
        print("\n🔍 Шаг 2: Фильтрация без GPT...")
        self.articles = self.filter.remove_advertorial(self.articles)
        self.articles = self.filter.filter_by_length(self.articles)
        print(f"📊 После фильтрации: {len(self.articles)} статей")
        
        if use_gpt and self.gpt:
            print("\n🧠 Шаг 3: GPT-5.5 фильтрация...")
            self.articles = self.gpt.filter_articles(
                self.articles,
                query=query,
                min_score=50
            )
            print(f"📊 После GPT: {len(self.articles)} статей")
        
        self.articles = self.articles[:limit]
        
        return self.articles
    
    def display_results(self):
        if not self.articles:
            print("\n❌ Нет статей для отображения")
            return
        
        print("\n" + "=" * 70)
        print(f"📊 РЕЗУЛЬТАТЫ: {len(self.articles)} СТАТЕЙ")
        print("=" * 70)
        
        for i, article in enumerate(self.articles, 1):
            print(f"\n{i}. 📝 {article.get('title', 'Без заголовка')}")
            print(f"   👤 {article.get('author', 'Неизвестен')}")
            
            if article.get('date'):
                print(f"   📅 {article.get('date')}")
            
            if article.get('tags'):
                print(f"   🏷️ {', '.join(article['tags'][:5])}")
            
            if 'gpt_analysis' in article:
                analysis = article['gpt_analysis']
                print(f"   🤖 GPT оценка: {analysis.get('score', 0)}%")
                print(f"   📌 {analysis.get('summary', '')}")
            
            if article.get('content_length'):
                print(f"   📄 {article['content_length']} символов")
            
            print(f"   🔗 {article.get('url', '')}")
            print("-" * 60)
    
    def save_results(self, filename: str = "habr_articles.json"):
        if not self.articles:
            print("❌ Нет данных для сохранения")
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.articles, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Результаты сохранены в {filename}")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")

async def main():
    
    print("=" * 70)
    print("🚀 HABR PARSER + GPT-5.5")
    print("=" * 70)
    
    app = HabrApp()
    
    query = input("\n🔍 Введите запрос (или Enter для 'нейросети'): ").strip()
    if not query:
        query = "нейросети"
    
    limit_input = input("📊 Количество статей (Enter для 10): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 10
    
    use_gpt = input("🧠 Использовать GPT-5.5? (y/n): ").strip().lower() == 'y'
    
    if use_gpt:
        api_key = input("🔑 Введите API ключ VseLLM: ").strip()
        if api_key:
            app.init_gpt(api_key)
        else:
            print("⚠️ Ключ не введен, GPT отключен")
            use_gpt = False
    
    articles = await app.search(query, limit, use_gpt)
    
    app.display_results()
    
    save = input("\n💾 Сохранить результаты? (y/n): ").strip().lower() == 'y'
    if save:
        app.save_results()
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Программа остановлена")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
