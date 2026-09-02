"""
Парсер Habr - одна простая программа
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import json
from datetime import datetime
import re


class HabrParser:
    """Простой парсер Habr"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.rss_feeds = [
            "https://habr.com/ru/rss/all/",
            "https://habr.com/ru/rss/interesting/",
        ]
        
    async def search(self, query: str, limit: int = 10):
        """Поиск статей"""
        print(f"\n🔍 Ищем: '{query}'")
        
        all_articles = []
        seen_urls = set()
        
        async with aiohttp.ClientSession() as session:
            # Загружаем RSS ленты
            for feed_url in self.rss_feeds:
                try:
                    async with session.get(feed_url, headers=self.headers, timeout=15) as response:
                        if response.status == 200:
                            content = await response.text()
                            articles = self._parse_rss(content)
                            
                            for article in articles:
                                url = article.get('url')
                                if url and url not in seen_urls:
                                    seen_urls.add(url)
                                    all_articles.append(article)
                except Exception as e:
                    print(f"  ⚠️ Ошибка {feed_url}: {e}")
            
            print(f"  📊 Найдено {len(all_articles)} статей")
            
            # Фильтруем по запросу
            if query:
                filtered = []
                for article in all_articles:
                    text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
                    if all(word in text for word in query.lower().split()):
                        filtered.append(article)
                all_articles = filtered
                print(f"  🔍 После фильтрации: {len(all_articles)} статей")
            
            # Получаем полный текст для каждой статьи
            print(f"\n📖 Загружаем полные статьи...")
            for i, article in enumerate(all_articles[:limit], 1):
                print(f"  {i}/{min(limit, len(all_articles))}: {article.get('title', '')[:50]}...")
                
                full = await self._get_full_article(session, article.get('url'))
                if full:
                    article['content'] = full.get('content', '')
                    article['content_length'] = len(article.get('content', ''))
            
            return all_articles[:limit]
    
    def _parse_rss(self, content):
        """Парсим RSS"""
        articles = []
        
        try:
            root = ET.fromstring(content)
            for item in root.findall('.//item'):
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
                
                if article.get('url') and article.get('title'):
                    articles.append(article)
                    
        except:
            pass
            
        return articles
    
    async def _get_full_article(self, session, url):
        """Получаем полный текст статьи"""
        try:
            async with session.get(url, headers=self.headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content = ""
                    for selector in ['div.post__text', 'div.article__body', 'div.content']:
                        for elem in soup.select(selector):
                            text = elem.get_text(separator=' ', strip=True)
                            if text and len(text) > 50:
                                content += text + " "
                    
                    if not content or len(content) < 100:
                        for p in soup.find_all('p'):
                            text = p.get_text(strip=True)
                            if len(text) > 50:
                                content += text + " "
                    
                    return {'content': ' '.join(content.split())}
        except:
            return None


async def main():
    """Запуск"""
    print("=" * 70)
    print("🚀 HABR ПАРСЕР")
    print("=" * 70)
    
    # Ввод запроса
    query = input("\n🔍 Введите запрос: ").strip()
    if not query:
        print("❌ Запрос не может быть пустым!")
        return
    
    # Ввод количества
    try:
        limit = int(input("📊 Сколько статей (по умолчанию 10): ") or "10")
    except:
        limit = 10
    
    # Парсим
    parser = HabrParser()
    articles = await parser.search(query, limit)
    
    # Выводим результат
    print("\n" + "=" * 70)
    print(f"📊 Найдено: {len(articles)} статей")
    print("=" * 70)
    
    if articles:
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. 📝 {article.get('title', 'Без заголовка')}")
            print(f"   👤 {article.get('author', 'Неизвестен')}")
            if article.get('date'):
                print(f"   📅 {article.get('date')}")
            if article.get('tags'):
                print(f"   🏷️ {', '.join(article['tags'][:5])}")
            if article.get('description'):
                print(f"   📝 {article['description'][:150]}...")
            print(f"   🔗 {article.get('url', '')}")
            print("-" * 60)
        
        # Сохраняем
        save = input("\n💾 Сохранить в JSON? (y/n): ").lower()
        if save == 'y':
            filename = f"habr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Очищаем для сохранения
            save_articles = []
            for a in articles:
                a_copy = a.copy()
                if 'content' in a_copy:
                    del a_copy['content']
                save_articles.append(a_copy)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'query': query,
                    'total': len(articles),
                    'articles': save_articles
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Сохранено в {filename}")
    else:
        print("\n❌ Статьи не найдены")
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Остановлено")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
