import openai
import time
import json
import re
import hashlib
from typing import List, Dict, Optional


class GPTProcessor:
    
    def __init__(self, api_key: str, base_url: str = "https://api.vsellm.ru/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        self.model = "openai/gpt-5.5"
        
        try:
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except Exception as e:
            print(f"❌ Ошибка GPT: {e}")
    
    def filter_articles(self, articles: List[Dict], query: str, min_score: int = 50) -> List[Dict]:
        if not self.client:
            print("⚠️ GPT не доступен")
            return articles
        
        filtered = []
        
        for i, article in enumerate(articles, 1):
            print(f"  Анализ {i}/{len(articles)}...")
            
            analysis = self._analyze(article, query)
            
            if analysis and analysis.get('relevance', False):
                score = analysis.get('relevance_score', 0)
                if score >= min_score:
                    article['gpt_analysis'] = {
                        'score': score,
                        'summary': analysis.get('summary', ''),
                        'category': analysis.get('category', '')
                    }
                    filtered.append(article)
                    print(f"    ✅ {score}%")
                else:
                    print(f"    ❌ {score}% (ниже {min_score}%)")
            else:
                print(f"    ❌ Не релевантна")
            
            time.sleep(0.3)
        
        filtered.sort(key=lambda x: x.get('gpt_analysis', {}).get('score', 0), reverse=True)
        
        return filtered
    
    def _analyze(self, article: Dict, query: str) -> Optional[Dict]:
        prompt = f"""
        Проанализируй статью на релевантность запросу.
        
        Запрос: "{query}"
        
        Заголовок: {article.get('title', '')}
        Описание: {article.get('description', '')[:300]}
        Содержание: {article.get('content', '')[:500]}
        
        Ответь JSON:
        {{
            "relevance": true/false,
            "relevance_score": 0-100,
            "summary": "краткое содержание",
            "category": "категория"
        }}
        """
        
        messages = [
            {"role": "system", "content": "Ты - эксперт. Отвечай только JSON."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            print(f"    ⚠️ Ошибка: {e}")
        
        return None
