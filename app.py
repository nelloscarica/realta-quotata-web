from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
import pandas as pd
import statistics
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional

app = Flask(__name__)

class QuoteRealiCalculator:
    """Modulo di calcolo quote reali integrato"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_page_content(self, url: str):
        """Recupera il contenuto della pagina"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Errore nel recuperare {url}: {e}")
            return None
    
    def detect_site_version(self, soup):
        """Rileva se è il vecchio o nuovo sito"""
        if soup.find('table', class_='games-stat'):
            return 'new'
        elif soup.find('table', class_='gamesStat'):
            return 'old'
        else:
            return 'unknown'
    
    def extract_match_quotes(self, match_url: str) -> Dict:
        """Estrae le quote dai bookmaker per il match"""
        soup = self.get_page_content(match_url)
        if not soup:
            return {}
        
        version = self.detect_site_version(soup)
        
        if version == 'old':
            return self._extract_quotes_old_site(soup)
        elif version == 'new':
            return self._extract_quotes_new_site(soup)
        else:
            return {}
    
    def _extract_quotes_old_site(self, soup) -> Dict:
        """Estrae quote dal vecchio sito"""
        quotes = {
            '1': [], 'X': [], '2': [],
            'under_2_5': [], 'over_2_5': [],
            'bts_yes': [], 'bts_no': []
        }
        
        odds_table = soup.find('table', class_='odds')
        if not odds_table:
            return quotes
        
        rows = odds_table.find('tbody').find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 16:
                try:
                    if cells[1].text.strip() and cells[1].text.strip() != '-':
                        quotes['1'].append(float(cells[1].text.strip()))
                    if cells[2].text.strip() and cells[2].text.strip() != '-':
                        quotes['X'].append(float(cells[2].text.strip()))
                    if cells[3].text.strip() and cells[3].text.strip() != '-':
                        quotes['2'].append(float(cells[3].text.strip()))
                    if cells[7].text.strip() and cells[7].text.strip() != '-':
                        quotes['under_2_5'].append(float(cells[7].text.strip()))
                    if cells[8].text.strip() and cells[8].text.strip() != '-':
                        quotes['over_2_5'].append(float(cells[8].text.strip()))
                    if cells[14].text.strip() and cells[14].text.strip() != '-':
                        quotes['bts_yes'].append(float(cells[14].text.strip()))
                    if cells[15].text.strip() and cells[15].text.strip() != '-':
                        quotes['bts_no'].append(float(cells[15].text.strip()))
                except (ValueError, IndexError):
                    continue
        
        return quotes
    
    def _extract_quotes_new_site(self, soup) -> Dict:
        """Estrae quote dal nuovo sito"""
        quotes = {
            '1': [], 'X': [], '2': [],
            'under_2_5': [], 'over_2_5': [],
            'bts_yes': [], 'bts_no': []
        }
        
        game_odds = soup.find('div', class_='game-odds')
        if not game_odds:
            return quotes
        
        self._extract_1x2_new(game_odds, quotes)
        self._extract_over_under_new(game_odds, quotes)
        self._extract_bts_new(game_odds, quotes)
        
        return quotes
    
    def _extract_1x2_new(self, container, quotes):
        """Estrae quote 1X2 dal nuovo sito"""
        for table in container.find_all('table', class_='odds'):
            header = table.find('th', class_='odds-type')
            if header and 'Standard 1X2' in header.text:
                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    cells = row.find_all('td', class_='odd')
                    if len(cells) >= 3:
                        try:
                            quotes['1'].append(float(cells[0].text.strip()))
                            quotes['X'].append(float(cells[1].text.strip()))
                            quotes['2'].append(float(cells[2].text.strip()))
                        except ValueError:
                            continue
    
    def _extract_over_under_new(self, container, quotes):
        """Estrae quote Over/Under dal nuovo sito"""
        for table in container.find_all('table', class_='odds'):
            header = table.find('th', class_='odds-type')
            if header and 'Over/Under' in header.text:
                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    goal_cell = row.find('td', class_='center')
                    if goal_cell and goal_cell.text.strip() == '2.5':
                        cells = row.find_all('td', class_='odd')
                        if len(cells) >= 2:
                            try:
                                quotes['under_2_5'].append(float(cells[0].text.strip()))
                                quotes['over_2_5'].append(float(cells[1].text.strip()))
                            except ValueError:
                                continue
    
    def _extract_bts_new(self, container, quotes):
        """Estrae quote BTS dal nuovo sito"""
        for table in container.find_all('table', class_='odds'):
            header = table.find('th', class_='odds-type')
            if header and 'BTS' in header.text:
                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    cells = row.find_all('td', class_='odd')
                    if len(cells) >= 2:
                        try:
                            quotes['bts_yes'].append(float(cells[0].text.strip()))
                            quotes['bts_no'].append(float(cells[1].text.strip()))
                        except ValueError:
                            continue
    
    def extract_team_stats_complete(self, base_team_url: str) -> Dict:
        """Estrae statistiche complete usando tutti gli URL specifici"""
        stats = {
            'all_matches': [],
            'home_matches': [],
            'away_matches': [],
            'last_5_all': [],
            'last_5_home': [],
            'last_5_away': []
        }
        
        urls = {
            'all_matches': base_team_url,
            'home_matches': f"{base_team_url}/league-home",
            'away_matches': f"{base_team_url}/league-away",
        }
        
        for category, url in urls.items():
            try:
                soup = self.get_page_content(url)
                if soup:
                    matches = self._extract_matches_from_page(soup, category)
                    stats[category] = matches
            except Exception as e:
                continue
        
        if stats['all_matches']:
            stats['last_5_all'] = stats['all_matches'][:5] if len(stats['all_matches']) >= 5 else stats['all_matches']
        
        if stats['home_matches']:
            stats['last_5_home'] = stats['home_matches'][:5] if len(stats['home_matches']) >= 5 else stats['home_matches']
        
        if stats['away_matches']:
            stats['last_5_away'] = stats['away_matches'][:5] if len(stats['away_matches']) >= 5 else stats['away_matches']
        
        return stats
    
    def _extract_matches_from_page(self, soup, category: str) -> List[Dict]:
        """Estrae partite da una pagina specifica"""
        matches = []
        
        version = self.detect_site_version(soup)
        
        if version == 'old':
            table = soup.find('table', class_='gamesStat')
        elif version == 'new':
            table = soup.find('table', class_='games-stat')
        else:
            return matches
        
        if not table:
            return matches
        
        rows = table.find('tbody').find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 5:
                try:
                    match_data = self._parse_match_row_universal(cells, category, version)
                    if match_data:
                        matches.append(match_data)
                except Exception as e:
                    continue
        
        return matches
    
    def _parse_match_row_universal(self, cells, category: str, version: str) -> Optional[Dict]:
        """Parser universale per tutte le pagine"""
        try:
            result_text = cells[3].text.strip()
            if ' - ' not in result_text:
                return None
                
            home_goals, away_goals = map(int, result_text.split(' - '))
            total_goals = home_goals + away_goals
            
            if category == 'home_matches':
                is_home = True
                team_result = 'W' if home_goals > away_goals else ('L' if home_goals < away_goals else 'D')
            elif category == 'away_matches':
                is_home = False
                team_result = 'W' if away_goals > home_goals else ('L' if away_goals < home_goals else 'D')
            else:
                if version == 'old':
                    is_home = bool(cells[2].find('span', class_='bold'))
                else:
                    is_home = 'bold' in cells[2].get('class', [])
                
                if is_home:
                    team_result = 'W' if home_goals > away_goals else ('L' if home_goals < away_goals else 'D')
                else:
                    team_result = 'W' if away_goals > home_goals else ('L' if away_goals < home_goals else 'D')
            
            return {
                'result': team_result,
                'total_goals': total_goals,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'both_scored': home_goals > 0 and away_goals > 0,
                'is_home': is_home,
                'category': category
            }
        except Exception as e:
            return None
    
    def _check_minimum_matches(self, home_stats: Dict, away_stats: Dict) -> bool:
        """Controlla che entrambe le squadre abbiano almeno 5 partite nelle rispettive posizioni"""
        home_matches_count = len(home_stats.get('home_matches', []))
        away_matches_count = len(away_stats.get('away_matches', []))
        
        return home_matches_count >= 5 and away_matches_count >= 5
    
    def calculate_probabilities_precise(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Calcola probabilità usando i dati precisi dalle pagine specifiche"""
        if not self._check_minimum_matches(home_stats, away_stats):
            return {"error": "Dati insufficienti - Minimo 5 partite richieste per ogni squadra"}
        
        probabilities = {}
        
        prob_1x2 = self._calculate_1x2_probabilities_precise(home_stats, away_stats)
        probabilities.update(prob_1x2)
        
        prob_ou = self._calculate_over_under_probabilities_precise(home_stats, away_stats)
        probabilities.update(prob_ou)
        
        prob_bts = self._calculate_bts_probabilities_precise(home_stats, away_stats)
        probabilities.update(prob_bts)
        
        return probabilities
    
    def _calculate_1x2_probabilities_precise(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Calcola probabilità 1X2"""
        percentages_1 = []
        percentages_2 = []
        percentages_x = []
        
        categories = [
            ('all_matches', 'all_matches'),
            ('last_5_all', 'last_5_all'),
            ('home_matches', 'away_matches'),
            ('last_5_home', 'last_5_away')
        ]
        
        for i, (home_cat, away_cat) in enumerate(categories):
            home_matches = home_stats.get(home_cat, [])
            away_matches = away_stats.get(away_cat, [])
            
            if home_matches and away_matches:
                home_wins = sum(1 for m in home_matches if m['result'] == 'W')
                away_losses = sum(1 for m in away_matches if m['result'] == 'L')
                total_matches = len(home_matches) + len(away_matches)
                
                away_wins = sum(1 for m in away_matches if m['result'] == 'W')
                home_losses = sum(1 for m in home_matches if m['result'] == 'L')
                
                if total_matches > 0:
                    prob_1_raw = (home_wins + away_losses) / total_matches
                    prob_2_raw = (away_wins + home_losses) / total_matches
                    prob_x_raw = 1 - (prob_1_raw + prob_2_raw)
                    
                    percentages_1.append(prob_1_raw * 100)
                    percentages_2.append(prob_2_raw * 100)
                    percentages_x.append(prob_x_raw * 100)
        
        avg_prob_1 = sum(percentages_1) / len(percentages_1) if percentages_1 else 0
        avg_prob_2 = sum(percentages_2) / len(percentages_2) if percentages_2 else 0
        avg_prob_x = sum(percentages_x) / len(percentages_x) if percentages_x else 0
        
        std_1 = statistics.stdev(percentages_1) if len(percentages_1) > 1 else 0
        std_2 = statistics.stdev(percentages_2) if len(percentages_2) > 1 else 0
        std_x = statistics.stdev(percentages_x) if len(percentages_x) > 1 else 0
        
        return {
            '1_probability': avg_prob_1,
            'X_probability': avg_prob_x,
            '2_probability': avg_prob_2,
            '1_std': std_1 / 100,
            'X_std': std_x / 100,
            '2_std': std_2 / 100
        }
    
    def _calculate_over_under_probabilities_precise(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Calcola probabilità Over/Under 2.5"""
        percentages_under = []
        
        categories = [
            ('all_matches', 'all_matches'),
            ('last_5_all', 'last_5_all'),
            ('home_matches', 'away_matches'),
            ('last_5_home', 'last_5_away')
        ]
        
        for home_cat, away_cat in categories:
            home_matches = home_stats.get(home_cat, [])
            away_matches = away_stats.get(away_cat, [])
            
            if home_matches and away_matches:
                home_under = sum(1 for m in home_matches if m['total_goals'] <= 2)
                away_under = sum(1 for m in away_matches if m['total_goals'] <= 2)
                total_matches = len(home_matches) + len(away_matches)
                
                if total_matches > 0:
                    perc_under = (home_under + away_under) / total_matches * 100
                    percentages_under.append(perc_under)
        
        avg_under = sum(percentages_under) / len(percentages_under) if percentages_under else 0
        avg_over = 100 - avg_under
        std_under = statistics.stdev(percentages_under) if len(percentages_under) > 1 else 0
        
        return {
            'under_2_5_probability': avg_under,
            'over_2_5_probability': avg_over,
            'under_2_5_std': std_under / 100,
            'over_2_5_std': std_under / 100
        }
    
    def _calculate_bts_probabilities_precise(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Calcola probabilità BTS"""
        percentages_bts_yes = []
        
        categories = [
            ('all_matches', 'all_matches'),
            ('last_5_all', 'last_5_all'),
            ('home_matches', 'away_matches'),
            ('last_5_home', 'last_5_away')
        ]
        
        for home_cat, away_cat in categories:
            home_matches = home_stats.get(home_cat, [])
            away_matches = away_stats.get(away_cat, [])
            
            if home_matches and away_matches:
                home_bts = sum(1 for m in home_matches if m['both_scored'])
                away_bts = sum(1 for m in away_matches if m['both_scored'])
                total_matches = len(home_matches) + len(away_matches)
                
                if total_matches > 0:
                    perc_bts = (home_bts + away_bts) / total_matches * 100
                    percentages_bts_yes.append(perc_bts)
        
        avg_bts_yes = sum(percentages_bts_yes) / len(percentages_bts_yes) if percentages_bts_yes else 0
        avg_bts_no = 100 - avg_bts_yes
        std_bts = statistics.stdev(percentages_bts_yes) if len(percentages_bts_yes) > 1 else 0
        
        return {
            'bts_yes_probability': avg_bts_yes,
            'bts_no_probability': avg_bts_no,
            'bts_yes_std': std_bts / 100,
            'bts_no_std': std_bts / 100
        }
    
    def calculate_real_odds(self, probabilities: Dict) -> Dict:
        """Converte probabilità in quote reali"""
        real_odds = {}
        
        for market, prob in probabilities.items():
            if '_probability' in market and prob > 0:
                odds_key = market.replace('_probability', '_real_odds')
                real_odds[odds_key] = round(100 / prob, 2)
        
        return real_odds
    
    def calculate_value_bets(self, real_odds: Dict, bookmaker_odds: Dict, probabilities: Dict) -> Dict:
        """Calcola value bet con filtri"""
        value_bets = {}
        
        mapping = {
            '1_real_odds': ('1', '1_std'),
            'X_real_odds': ('X', 'X_std'), 
            '2_real_odds': ('2', '2_std'),
            'under_2_5_real_odds': ('under_2_5', 'under_2_5_std'),
            'over_2_5_real_odds': ('over_2_5', 'over_2_5_std'),
            'bts_yes_real_odds': ('bts_yes', 'bts_yes_std'),
            'bts_no_real_odds': ('bts_no', 'bts_no_std')
        }
        
        for real_key, (book_key, std_key) in mapping.items():
            if real_key in real_odds and book_key in bookmaker_odds:
                real_odd = real_odds[real_key]
                book_odds = bookmaker_odds[book_key]
                std_dev = probabilities.get(std_key, 1.0)
                
                if book_odds:
                    max_book_odd = max(book_odds)
                    avg_book_odd = sum(book_odds) / len(book_odds)
                    absolute_deviation = abs(avg_book_odd - real_odd)
                    
                    if std_dev < 0.15 and absolute_deviation >= 0.5 and avg_book_odd > real_odd:
                        value_bets[book_key] = {
                            'real_odds': real_odd,
                            'best_book_odds': max_book_odd,
                            'avg_book_odds': round(avg_book_odd, 2),
                            'absolute_deviation': round(absolute_deviation, 2),
                            'std_deviation': round(std_dev, 6),
                            'is_value': True,
                            'value_percentage': round(((avg_book_odd - real_odd) / real_odd) * 100, 2) if real_odd > 0 else 0
                        }
        
        return value_bets
    
    def _extract_team_urls_from_match(self, match_url: str) -> Optional[Tuple[str, str]]:
        """Estrae gli URL delle squadre dall'URL del match"""
        try:
            match_part = match_url.split('/')[-1]
            
            if '-' in match_part:
                parts = match_part.split('-')
                if parts[-1].isdigit():
                    match_without_id = '-'.join(parts[:-1])
                else:
                    match_without_id = match_part
            else:
                match_without_id = match_part
            
            league_patterns = [
                'premier-league-england', 'championship-england',
                'ligue-1-france', 'ligue-2-france',
                '2-bundesliga-germany', 'bundesliga-germany',
                'serie-a-italy', 'serie-b-italy',
                'primera-division-spain', 'segunda-division-spain',
                'bundesliga-austria', 'pro-league-belgium',
                'prva-hnl-croatia', 'first-pfl-bulgaria',
                'first-league-czech-republic',
                'eredivisie-netherlands', 'eerste-divisie-netherlands',
                'ekstraklasa-poland', 'primeira-liga-portugal',
                'liga-portugal-2', 'liga-i-romania',
                'premiership-scotland', 'swiss-super-league-switzerland',
                'super-lig-turkiye', '1-division-norway', 'eliteserien-norway',
                'allsvenskan-sweden', 'superettan-sweden',
                'serie-a-brazil', 'serie-b-brazil',
                'veikkausliiga-finland', 'premier-league-iceland',
                'premier-division-ireland', 'nifl-premiership-northern-ireland'
            ]
            
            teams_part = match_without_id
            league_found = None
            
            for pattern in league_patterns:
                if f'-{pattern}' in match_without_id:
                    teams_part = match_without_id.replace(f'-{pattern}', '')
                    league_found = pattern
                    break
                elif match_without_id.endswith(f'-{pattern}'):
                    teams_part = match_without_id.replace(f'-{pattern}', '')
                    league_found = pattern
                    break
            
            if not league_found:
                return None
            
            teams = teams_part.split('-')
            
            for i in range(1, len(teams)):
                home_team = '-'.join(teams[:i])
                away_team = '-'.join(teams[i:])
                
                if not home_team or not away_team:
                    continue
                
                country = self._get_country_from_league(league_found)
                
                home_url = f"https://tipsterarea.com/teams/{country}/{home_team}"
                away_url = f"https://tipsterarea.com/teams/{country}/{away_team}"
                
                if self._test_team_url(home_url) and self._test_team_url(away_url):
                    return home_url, away_url
            
            return None
            
        except Exception as e:
            print(f"Errore nell'estrazione URL squadre: {e}")
            return None
    
    def _get_country_from_league(self, league_found):
        """Determina il paese dalla lega trovata"""
        country_mapping = {
            'premier-league-england': 'england', 'championship-england': 'england',
            'ligue-1-france': 'france', 'ligue-2-france': 'france',
            'bundesliga-germany': 'germany', '2-bundesliga-germany': 'germany',
            'serie-a-italy': 'italy', 'serie-b-italy': 'italy',
            'primera-division-spain': 'spain', 'segunda-division-spain': 'spain',
            'bundesliga-austria': 'austria', 'pro-league-belgium': 'belgium',
            'prva-hnl-croatia': 'croatia', 'first-pfl-bulgaria': 'bulgaria',
            'first-league-czech-republic': 'czech-republic',
            'eredivisie-netherlands': 'netherlands', 'eerste-divisie-netherlands': 'netherlands',
            'ekstraklasa-poland': 'poland', 'primeira-liga-portugal': 'portugal',
            'liga-portugal-2': 'portugal', 'liga-i-romania': 'romania',
            'premiership-scotland': 'scotland', 'swiss-super-league-switzerland': 'switzerland',
            'super-lig-turkiye': 'turkiye', '1-division-norway': 'norway', 'eliteserien-norway':'norway',
            'allsvenskan-sweden':'sweden', 'superettan-sweden': 'sweden',
            'serie-a-brazil' : 'brazil', 'serie-b-brazil' : 'brazil',
            'veikkausliiga-finland' : 'finland', 'premier-league-iceland' : 'iceland',
            'premier-division-ireland' : 'ireland', 'nifl-premiership-northern-ireland': 'northern-ireland'
        }
        
        return country_mapping.get(league_found, 'england')
    
    def _test_team_url(self, url: str) -> bool:
        """Test per verificare se l'URL della squadra è valido"""
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def analyze_match_quick(self, match_url: str) -> Dict:
        """Analisi rapida di una partita per l'integrazione web"""
        try:
            print(f"🔍 Analizzando: {match_url}")
            
            # Estrai quote bookmaker
            bookmaker_odds = self.extract_match_quotes(match_url)
            
            # Estrai URL delle squadre  
            team_urls = self._extract_team_urls_from_match(match_url)
            if not team_urls:
                return {"error": "URL squadre non trovati"}
            
            home_url, away_url = team_urls
            
            # Estrai statistiche squadre
            home_stats = self.extract_team_stats_complete(home_url)
            away_stats = self.extract_team_stats_complete(away_url)
            
            if not home_stats or not away_stats:
                return {"error": "Statistiche squadre non disponibili"}
            
            # Calcola probabilità
            probabilities = self.calculate_probabilities_precise(home_stats, away_stats)
            
            if 'error' in probabilities:
                return {"error": probabilities['error']}
            
            # Calcola quote reali
            real_odds = self.calculate_real_odds(probabilities)
            
            # Calcola value bet
            value_bets = self.calculate_value_bets(real_odds, bookmaker_odds, probabilities)
            
            return {
                'success': True,
                'probabilities': probabilities,
                'value_bets': value_bets,
                'num_value_bets': len(value_bets)
            }
        except Exception as e:
            return {"error": str(e)}

# Inizializza il calculator
calculator = QuoteRealiCalculator()

def scrape_palinsesto(data_str="today"):
    """Carica il palinsesto per una data specifica"""
    if data_str == "today":
        data = datetime.now()
    else:
        # Formato: dd-mm-yyyy
        data = datetime.strptime(data_str, '%d-%m-%Y')
    
    url = f"https://tipsterarea.com/matches/date-{data.strftime('%d-%m-%Y')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        partite = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/match/" in href:
                teams = a.find("span", class_="teams")
                if not teams:
                    continue
                home = teams.find("span", class_="home")
                away = teams.find("span", class_="away")
                if not home or not away:
                    continue
                home = home.text.strip()
                away = away.text.strip()

                time_span = a.find("span", class_="time")
                if not time_span:
                    continue
                time = time_span.text.strip()

                odds = a.find("span", class_="odds")
                if not odds:
                    continue
                o1 = odds.find("span", class_="o1")
                oX = odds.find("span", class_="oX")
                o2 = odds.find("span", class_="o2")
                if not o1 or not oX or not o2:
                    continue
                o1 = o1.text.strip()
                oX = oX.text.strip()
                o2 = o2.text.strip()

                league_div = a.find_previous("div", class_="league-header")
                if not league_div:
                    continue
                lega = league_div.get_text(strip=True)
                
                partite.append({
                    "lega": lega,
                    "ora": time,
                    "casa": home,
                    "trasferta": away,
                    "quote": {"1": o1, "X": oX, "2": o2},
                    "url_reale": f"https://tipsterarea.com{href}"
                })

        return partite
    except Exception as e:
        print(f"Errore caricamento palinsesto: {e}")
        return []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/palinsesto')
def get_palinsesto():
    """API per ottenere il palinsesto"""
    try:
        data_param = request.args.get('data', 'today')
        partite = scrape_palinsesto(data_param)
        return jsonify({
            "success": True,
            "partite": partite,
            "count": len(partite)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route('/api/analisi-custom', methods=['POST'])
def analisi_custom():
    """API per analizzare partite selezionate dall'utente"""
    try:
        data = request.get_json()
        partite_selezionate = data.get('partite', [])
        
        if not partite_selezionate:
            return jsonify({
                "success": False,
                "error": "Nessuna partita selezionata"
            })
        
        print(f"🔍 Analizzando {len(partite_selezionate)} partite selezionate dall'utente")
        
        partite_processate = []
        value_bets_found = []
        contatori = {
            'analizzate': 0,
            'value_bets': 0,
            'dati_insufficienti': 0,
            'errori': 0
        }
        
        for i, partita in enumerate(partite_selezionate):
            print(f"📊 Analizzando {i+1}/{len(partite_selezionate)}: {partita['casa']} vs {partita['trasferta']}")
            
            risultato = calculator.analyze_match_quick(partita['url_reale'])
            
            partita_info = {
                "lega": partita['lega'],
                "ora": partita['ora'],
                "casa": partita['casa'],
                "trasferta": partita['trasferta'],
                "quote_1x2": partita['quote']
            }
            
            if 'success' in risultato:
                value_bets = risultato.get('value_bets', {})
                probabilities = risultato.get('probabilities', {})
                
                contatori['analizzate'] += 1
                
                if len(value_bets) > 0:
                    contatori['value_bets'] += 1
                    partita_info.update({
                        "status": f"✅ {len(value_bets)} VB",
                        "value_bets": value_bets,
                        "probabilities": probabilities,
                        "num_value_bets": len(value_bets)
                    })
                    value_bets_found.append(partita_info)
                else:
                    partita_info.update({
                        "status": "⚪ OK",
                        "value_bets": {},
                        "probabilities": probabilities,
                        "num_value_bets": 0
                    })
            
            elif 'error' in risultato:
                error_msg = risultato['error']
                if "Dati insufficienti" in error_msg or "Minimo 5 partite" in error_msg:
                    contatori['dati_insufficienti'] += 1
                    partita_info.update({
                        "status": "⚠️ <5 partite",
                        "value_bets": {},
                        "probabilities": {},
                        "num_value_bets": 0
                    })
                else:
                    contatori['errori'] += 1
                    partita_info.update({
                        "status": f"❌ Errore",
                        "value_bets": {},
                        "probabilities": {},
                        "num_value_bets": 0
                    })
            
            partite_processate.append(partita_info)
            
            # Piccola pausa per non sovraccaricare
            time.sleep(0.3)
        
        return jsonify({
            "success": True,
            "partite_selezionate": len(partite_selezionate),
            "partite_analizzate": contatori['analizzate'],
            "value_bets_found": contatori['value_bets'],
            "dati_insufficienti": contatori['dati_insufficienti'],
            "errori": contatori['errori'],
            "partite": partite_processate,
            "solo_value_bets": value_bets_found
        })
        
    except Exception as e:
        print(f"❌ Errore nell'analisi custom: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
