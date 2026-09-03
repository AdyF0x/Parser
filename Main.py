import requests
import json
import time
from typing import List, Dict, Optional
from datetime import datetime

from config import (
    DADATA_API_KEY,
    DADATA_SECRET_KEY,
    DEFAULT_LIMIT,
    OUTPUT_FILE,
    VERBOSE,
    check_config
)


class EgrulParser:
    
    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_key = api_key or DADATA_API_KEY
        self.secret_key = secret_key or DADATA_SECRET_KEY
        self.base_url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"
        
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.api_key}",
        }
        
        if self.secret_key:
            self.headers["X-Secret"] = self.secret_key
        
        self._check_api_key()
    
    def _check_api_key(self):
        if self.api_key == "ваш_ключ_от_dadata":
            print("⚠️ ВНИМАНИЕ: DaData API ключ не настроен!")
            print("   Получите ключ на https://dadata.ru")
            print("   И вставьте его в config.py")
    
    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> List[Dict]:
        if VERBOSE:
            print(f"🔍 Поиск: '{query}' (лимит: {limit})")
        
        if self._is_inn(query):
            result = self._search_by_inn(query)
            return [result] if result else []
        
        elif self._is_ogrn(query):
            result = self._search_by_ogrn(query)
            return [result] if result else []
        
        else:
            return self._search_by_name(query, limit)
    
    def _is_inn(self, query: str) -> bool:
        return query.isdigit() and len(query) in [10, 12]
    
    def _is_ogrn(self, query: str) -> bool:
        return query.isdigit() and len(query) in [13, 15]
    
    def _search_by_inn(self, inn: str) -> Optional[Dict]:
        url = f"{self.base_url}/findById/party"
        payload = {"query": inn, "branch_type": "MAIN"}
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", [])
                if suggestions:
                    if VERBOSE:
                        print(f"   ✅ Компания найдена")
                    return self._parse_company(suggestions[0])
                else:
                    if VERBOSE:
                        print(f"   ❌ Компания с ИНН {inn} не найдена")
                    return None
            else:
                if VERBOSE:
                    print(f"   ❌ Ошибка API: {response.status_code}")
                return None
            
        except Exception as e:
            if VERBOSE:
                print(f"   ❌ Ошибка: {e}")
            return None
    
    def _search_by_ogrn(self, ogrn: str) -> Optional[Dict]:
        url = f"{self.base_url}/suggest/party"
        payload = {"query": ogrn, "count": 1, "branch_type": "MAIN"}
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", [])
                if suggestions:
                    if VERBOSE:
                        print(f"   ✅ Компания найдена")
                    return self._parse_company(suggestions[0])
                else:
                    if VERBOSE:
                        print(f"   ❌ Компания с ОГРН {ogrn} не найдена")
                    return None
            else:
                if VERBOSE:
                    print(f"   ❌ Ошибка API: {response.status_code}")
                return None
            
        except Exception as e:
            if VERBOSE:
                print(f"   ❌ Ошибка: {e}")
            return None
    
    def _search_by_name(self, name: str, limit: int) -> List[Dict]:
        """Поиск по названию"""
        url = f"{self.base_url}/suggest/party"
        payload = {
            "query": name,
            "count": limit,
            "branch_type": "MAIN",
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", [])
                
                if suggestions:
                    if VERBOSE:
                        print(f"   ✅ Найдено {len(suggestions)} компаний")
                    return [self._parse_company(s) for s in suggestions]
                else:
                    if VERBOSE:
                        print(f"   ❌ Компании не найдены")
                    return []
            else:
                if VERBOSE:
                    print(f"   ❌ Ошибка API: {response.status_code}")
                return []
            
        except Exception as e:
            if VERBOSE:
                print(f"   ❌ Ошибка: {e}")
            return []
    
    def _parse_company(self, suggestion: Dict) -> Dict:
        #Парсинг данных компании
        if not suggestion:
            return {}
        
        data = suggestion.get("data", {})
        if not data:
            return {}
        
        # Функция конвертации даты из Unix timestamp
        def convert_date(timestamp_ms):
            if not timestamp_ms:
                return ""
            try:
                dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
                return dt.strftime("%d.%m.%Y")
            except:
                return str(timestamp_ms)
        
        # Статус
        state_data = data.get("state", {})
        status_raw = state_data.get("status", "")
        status_map = {
            'ACTIVE': 'Действующее',
            'LIQUIDATED': 'Ликвидировано',
            'LIQUIDATING': 'Ликвидируется',
            'BANKRUPT': 'Банкротство',
            'REORGANIZING': 'Реорганизуется',
        }
        status_text = status_map.get(status_raw, status_raw)
        
        # Название
        name_data = data.get("name", {})
        
        # Адрес
        address_data = data.get("address", {})
        address_unrestricted = address_data.get("unrestricted_value", "") if address_data else ""
        address_data_inner = address_data.get("data", {}) if address_data else {}
        
        # Руководство
        management_data = data.get("management", {})
        
        # Капитал
        capital_data = data.get("capital", {})
        
        # Телефоны
        phones = data.get("phones", [])
        phone = phones[0].get("value", "") if phones else ""
        
        # Email
        emails = data.get("emails", [])
        email = emails[0] if emails else ""
        
        # Учредители
        founders = data.get("founders", [])
        
        # Налоговый орган
        tax_data = data.get("tax_authority", {})
        
        company = {
            "inn": data.get("inn", ""),
            "ogrn": data.get("ogrn", ""),
            "kpp": data.get("kpp", ""),
            "name_full": name_data.get("full_with_opf", "") if name_data else "",
            "name_short": name_data.get("short_with_opf", "") if name_data else "",
            "status": status_raw,
            "status_text": status_text,
            "registration_date": convert_date(state_data.get("registration_date", "")),
            "liquidated_date": convert_date(state_data.get("liquidated_date", "")),
            "address_full": address_unrestricted,
            "address_region": address_data_inner.get("region", "") if address_data_inner else "",
            "address_city": address_data_inner.get("city", "") if address_data_inner else "",
            "director": management_data.get("name", "") if management_data else "",
            "director_position": management_data.get("post", "") if management_data else "",
            "capital": capital_data.get("value", 0) if capital_data else 0,
            "okved": data.get("okved", ""),
            "okved_type": data.get("okved_type", ""),
            "phone": phone,
            "email": email,
            "founders": founders,
            "branches_count": data.get("branch_count", 0),
            "tax_authority": tax_data.get("name", "") if tax_data else "",
            "tax_authority_code": tax_data.get("code", "") if tax_data else "",
        }
        
        return company
    
    def display_company(self, company: Dict, index: int = None):
        if not company:
            print("❌ Нет данных о компании")
            return
        
        prefix = f"{index}. " if index else ""
        
        name = company.get('name_full', 'Без названия')
        if not name:
            name = company.get('name_short', 'Без названия')
        
        print(f"\n{prefix}🏢 {name}")
        print(f"   📌 ИНН: {company.get('inn', 'Не указан')}")
        
        ogrn = company.get('ogrn', '')
        if ogrn:
            print(f"   📌 ОГРН: {ogrn}")
        
        kpp = company.get('kpp', '')
        if kpp:
            print(f"   📌 КПП: {kpp}")
        
        status = company.get('status_text', '')
        if status:
            print(f"   📌 Статус: {status}")
        
        if company.get('director'):
            print(f"   👤 Руководитель: {company.get('director')}")
            if company.get('director_position'):
                print(f"   📋 Должность: {company.get('director_position')}")
        
        if company.get('address_full'):
            print(f"   📍 {company.get('address_full')}")
        
        capital = company.get('capital', 0)
        if capital > 0:
            if capital >= 1000000:
                print(f"   💰 Уставный капитал: {capital/1000000:.1f} млн руб.")
            elif capital >= 1000:
                print(f"   💰 Уставный капитал: {capital/1000:.1f} тыс. руб.")
            else:
                print(f"   💰 Уставный капитал: {capital} руб.")
        
        if company.get('registration_date'):
            print(f"   📅 Дата регистрации: {company.get('registration_date')}")
        
        if company.get('liquidated_date'):
            print(f"   📅 Дата ликвидации: {company.get('liquidated_date')}")
        
        if company.get('branches_count', 0) > 0:
            print(f"   🏢 Филиалов: {company.get('branches_count')}")
        
        if company.get('okved'):
            print(f"   📋 ОКВЭД: {company.get('okved')}")
        
        if company.get('phone'):
            print(f"   📞 Телефон: {company.get('phone')}")
        
        if company.get('email'):
            print(f"   ✉️ Email: {company.get('email')}")
        
        if company.get('tax_authority'):
            print(f"   🏛️ Налоговый орган: {company.get('tax_authority')}")
        
        # Учредители
        founders = company.get('founders', [])
        if founders and len(founders) > 0:
            founder_names = []
            for f in founders[:3]:
                if isinstance(f, dict):
                    name = f.get('name', '')
                    if name:
                        founder_names.append(name)
                elif isinstance(f, str):
                    founder_names.append(f)
            if founder_names:
                print(f"   👥 Учредители: {', '.join(founder_names[:3])}")
                if len(founders) > 3:
                    print(f"   👥 ... и еще {len(founders) - 3}")
        
        print("-" * 50)


def main():
    print("=" * 70)
    print("🏢 ПАРСЕР ЕГРЮЛ (ЧЕРЕЗ DADATA)")
    print("=" * 70)
    
    # Проверка конфигурации
    check_config()
    
    parser = EgrulParser()
    
    print("\n💡 Примеры запросов:")
    print("   - ИНН: 7707083893 (Сбербанк)")
    print("   - ИНН: 7736207543 (Яндекс)")
    print("   - Название: Сбербанк")
    print("   - Название: Яндекс")
    print("   - ОГРН: 1027700132195")
    print("=" * 70)
    
    while True:
        try:
            query = input("\n🔍 Введите ИНН, ОГРН или название (или 'exit'): ").strip()
            
            if query.lower() == "exit":
                break
            
            if not query:
                continue
            
            # Запрос количества компаний
            limit_input = input("📊 Количество компаний (Enter для 10): ").strip()
            try:
                limit = int(limit_input) if limit_input else DEFAULT_LIMIT
                if limit < 1:
                    print("⚠️ Количество не может быть меньше 1. Использовано значение 1.")
                    limit = 1
                elif limit > 100:
                    print("⚠️ Количество не может быть больше 100. Использовано значение 100.")
                    limit = 100
            except ValueError:
                print(f"⚠️ Некорректный ввод. Использовано значение по умолчанию ({DEFAULT_LIMIT}).")
                limit = DEFAULT_LIMIT
            
            results = parser.search(query, limit=limit)
            
            if not results:
                print("❌ Ничего не найдено")
                continue
            
            print(f"\n📊 Найдено {len(results)} компаний:\n")
            
            for i, company in enumerate(results, 1):
                parser.display_company(company, i)
            

            print("\n" + "=" * 50)
            print("🧠 ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ:")
            print("=" * 50)
            
            # Проверяем наличие GPT ключа
            from config import VSELLM_API_KEY
            gpt_available = VSELLM_API_KEY and VSELLM_API_KEY != "ваш_ключ_от_vsellm"
            
            if gpt_available:
                analyze_choice = input("🔍 Проанализировать компании через GPT-5.5? (y/n): ").strip().lower()
                
                if analyze_choice == 'y':
                    print("\n🧠 Запуск GPT-5.5 анализа...")
                    try:
                        from GPT import GPTAnalyzer
                        analyzer = GPTAnalyzer(VSELLM_API_KEY)
                        
                        # Анализируем компании
                        results = analyzer.analyze_multiple(results)
                        
                        print("\n✅ Анализ завершен!\n")
                        
                        # Показываем обновленные данные с анализом
                        for i, company in enumerate(results, 1):
                            parser.display_company(company, i)
                            
                            if 'gpt_analysis' in company:
                                analysis = company['gpt_analysis']
                                print(f"\n   🤖 АНАЛИЗ РИСКОВ:")
                                print(f"   📊 Уровень риска: {analysis.get('risk_level', 'Неизвестно')} ({analysis.get('total_risk', 0)}%)")
                                
                                print(f"   📈 Детали:")
                                print(f"      • Кредитный риск: {analysis.get('credit_risk', 0)}%")
                                print(f"      • Финансовый риск: {analysis.get('financial_risk', 0)}%")
                                print(f"      • Юридический риск: {analysis.get('legal_risk', 0)}%")
                                print(f"      • Налоговый риск: {analysis.get('tax_risk', 0)}%")
                                
                                if analysis.get('summary'):
                                    print(f"   📌 {analysis.get('summary', '')}")
                                
                                if analysis.get('recommendations'):
                                    print(f"   💡 Рекомендации:")
                                    for rec in analysis.get('recommendations', [])[:3]:
                                        print(f"      • {rec}")
                                
                                print("-" * 50)
                    
                    except Exception as e:
                        print(f"❌ Ошибка GPT анализа: {e}")
            else:
                print("⚠️ GPT-5.5 не доступен (не настроен API ключ в config.py)")
                print("   Получите ключ на https://vsellm.ru и добавьте в config.py")
            
            save = input("\n💾 Сохранить результаты в JSON? (y/n): ").strip().lower()
            if save == 'y':
                filename = f"companies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"✅ Сохранено в {filename}")
        
        except KeyboardInterrupt:
            print("\n⏹️ Программа остановлена")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()