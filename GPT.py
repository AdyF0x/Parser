import openai
import json
import re
import time
import hashlib
from typing import List, Dict, Optional

from config import VSELLM_API_KEY, VERBOSE


class GPTAnalyzer:
    
    def __init__(self, api_key: str = None, model: str = "openai/gpt-5.5"):
        self.api_key = api_key or VSELLM_API_KEY
        self.model = model
        self.client = None
        self.cache = {}
        
        self._init_client()
    
    def _init_client(self):
        if self.api_key == "ваш_ключ_от_vsellm" or not self.api_key:
            if VERBOSE:
                print("⚠️ VseLLM API ключ не настроен!")
            return
        
        try:
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.vsellm.ru/v1"
            )
            if VERBOSE:
                print("✅ GPT-5.5 инициализирован")
        except Exception as e:
            if VERBOSE:
                print(f"❌ Ошибка GPT: {e}")
    
    def analyze_company(self, company: Dict) -> Dict:
        if not self.client:
            return self._get_default_analysis()
        
        prompt = self._build_prompt(company)
        
        try:
            response = self._call_gpt(prompt)
            if response:
                analysis = self._parse_json(response)
                if analysis:
                    return analysis
        except Exception as e:
            if VERBOSE:
                print(f"⚠️ Ошибка анализа: {e}")
        
        return self._get_default_analysis()
    
    def analyze_multiple(self, companies: List[Dict]) -> List[Dict]:
        if not self.client:
            if VERBOSE:
                print("⚠️ GPT не доступен, анализ пропущен")
            return companies
        
        results = []
        
        for i, company in enumerate(companies, 1):
            if VERBOSE:
                print(f"  Анализ {i}/{len(companies)}...")
            
            analysis = self.analyze_company(company)
            company['gpt_analysis'] = analysis
            results.append(company)
            time.sleep(0.5)
        
        return results
    
    def _build_prompt(self, company: Dict) -> str:
        return f"""
        Ты - эксперт по финансовому анализу и оценке рисков.
        Проведи комплексный анализ компании на основе данных из ЕГРЮЛ.
        
        Данные о компании:
        - Название: {company.get('name_full', 'Не указано')}
        - ИНН: {company.get('inn', 'Не указан')}
        - ОГРН: {company.get('ogrn', 'Не указан')}
        - КПП: {company.get('kpp', 'Не указан')}
        - Статус: {company.get('status_text', 'Не указан')}
        - Дата регистрации: {company.get('registration_date', 'Не указана')}
        - Дата прекращения: {company.get('liquidated_date', 'Не указана')}
        - Уставный капитал: {company.get('capital', 0)} руб.
        - Руководитель: {company.get('director', 'Не указан')}
        - Адрес: {company.get('address_full', 'Не указан')}
        - ОКВЭД: {company.get('okved', 'Не указан')}
        - Количество филиалов: {company.get('branches_count', 0)}
        - Налоговый орган: {company.get('tax_authority', 'Не указан')}
        
        Оцени каждый риск от 0 до 100:
        1. Кредитный риск - вероятность неисполнения обязательств
        2. Операционный риск - риск потерь из-за внутренних процессов
        3. Юридический риск - риск судебных разбирательств
        4. Репутационный риск - риск потери доверия
        5. Финансовый риск - риск банкротства
        6. Риск недобросовестности - риск мошенничества
        7. Налоговый риск - риск налоговых проблем
        8. Риск недействительности - риск недействительности документов
        
        Также определи:
        - Общий уровень риска (среднее значение)
        - Категорию риска: "Низкий", "Средний", "Высокий", "Критический"
        
        Ответь строго в формате JSON:
        {{
            "credit_risk": 0-100,
            "operational_risk": 0-100,
            "legal_risk": 0-100,
            "reputation_risk": 0-100,
            "financial_risk": 0-100,
            "fraud_risk": 0-100,
            "tax_risk": 0-100,
            "document_risk": 0-100,
            "total_risk": 0-100,
            "risk_level": "Низкий/Средний/Высокий/Критический",
            "summary": "краткое описание рисков",
            "recommendations": ["рекомендация1", "рекомендация2"],
            "red_flags": ["красный флаг1", "красный флаг2"],
            "positive_factors": ["позитивный фактор1", "позитивный фактор2"]
        }}
        """
    
    def _call_gpt(self, prompt: str) -> Optional[str]:
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Ты - эксперт по финансовому анализу. Отвечай только в формате JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=800
                )
                
                result = response.choices[0].message.content
                self.cache[cache_key] = result
                return result
                
            except Exception as e:
                if VERBOSE:
                    print(f"  ⚠️ Попытка {attempt + 1}/3: {e}")
                time.sleep(2 ** attempt)
        
        return None
    
    def _parse_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                try:
                    cleaned = re.sub(r'[\n\r\t]', ' ', text)
                    return json.loads(cleaned)
                except:
                    return None
        
        return None
    
    def _get_default_analysis(self) -> Dict:
        return {
            "credit_risk": 50,
            "operational_risk": 50,
            "legal_risk": 50,
            "reputation_risk": 50,
            "financial_risk": 50,
            "fraud_risk": 50,
            "tax_risk": 50,
            "document_risk": 50,
            "total_risk": 50,
            "risk_level": "Средний",
            "summary": "Недостаточно данных для полного анализа",
            "recommendations": ["Рекомендуется получить дополнительные данные"],
            "red_flags": ["Недостаточно информации"],
            "positive_factors": ["Данные получены из официального источника"]
        }


if __name__ == "__main__":
    # Тест
    print("=" * 60)
    print("🧠 ТЕСТ GPT АНАЛИЗА")
    print("=" * 60)
    
    if VSELLM_API_KEY == "ваш_ключ_от_vsellm" or not VSELLM_API_KEY:
        print("❌ VseLLM API ключ не настроен!")
        print("   Получите ключ на https://vsellm.ru")
        print("   И вставьте его в config.py")
    else:
        test_company = {
            "name_full": "ПАО СБЕРБАНК",
            "inn": "7707083893",
            "ogrn": "1027700132195",
            "kpp": "773601001",
            "status_text": "Действующее",
            "registration_date": "20.08.1991",
            "capital": 1000000000,
            "director": "Греф Герман Оскарович",
            "address_full": "г Москва, ул Вавилова, д 19",
            "branches_count": 100,
            "tax_authority": "Управление ФНС России по г. Москве"
        }
        
        analyzer = GPTAnalyzer()
        result = analyzer.analyze_company(test_company)
        
        print("\n📊 РЕЗУЛЬТАТ:")
        print(f"Уровень риска: {result.get('risk_level', 'Неизвестно')} ({result.get('total_risk', 0)}%)")
        print(f"📌 {result.get('summary', '')}")
        
        if result.get('recommendations'):
            print("\n💡 Рекомендации:")
            for rec in result.get('recommendations', []):
                print(f"  • {rec}")