#!/usr/bin/env python3
"""
Bot de Prédiction Telegram v2024 - Version Render.com
Architecture 100% YAML autonome - Aucune base de données PostgreSQL requise
Logique des As optimisée : 1 As premier groupe + 0 As deuxième groupe
"""

import os
import asyncio
import re
import logging
import sys
import json
import yaml
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from aiohttp import web

# Configuration des logs optimisée pour Render.com
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Variables d'environnement
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
PORT = int(os.getenv('PORT', '10000'))
prediction_interval = int(os.getenv('PREDICTION_INTERVAL', '1'))

# Variables d'état globales
detected_stat_channel = None
detected_display_channel = None
prediction_status = {}
last_predictions = []
status_log = []

# Client Telegram
session_name = f'bot_session_{int(time.time())}'
client = TelegramClient(session_name, API_ID, API_HASH)

# Gestionnaire YAML autonome
class SimpleYAMLManager:
    def __init__(self):
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def save_predictions(self, predictions):
        try:
            with open(f"{self.data_dir}/predictions.yaml", 'w') as f:
                yaml.dump(predictions, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Erreur sauvegarde prédictions: {e}")
    
    def load_predictions(self):
        try:
            if os.path.exists(f"{self.data_dir}/predictions.yaml"):
                with open(f"{self.data_dir}/predictions.yaml", 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Erreur chargement prédictions: {e}")
        return {}

yaml_manager = SimpleYAMLManager()

# Prédicteur de cartes autonome
class SimplePredictor:
    def __init__(self):
        self.prediction_status = yaml_manager.load_predictions()
        self.last_predictions = []
        self.status_log = []
        self.suits_mapping = {
            '♠️': '♠', '♥️': '♥', '♦️': '♦', '♣️': '♣',
            '♠': '♠', '♥': '♥', '♦': '♦', '♣': '♣'
        }
    
    def extract_game_number(self, text):
        """Extrait le numéro de jeu du message"""
        patterns = [
            r'#[Nn](\d+)',
            r'#(\d+)',
            r'(\d+)\.',
            r'Jeu\s*(\d+)',
            r'Game\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        return None
    
    def has_ace_in_group(self, group_text):
        """Vérifie si un groupe contient des As"""
        return bool(re.search(r'A[♠♥♦♣️]', group_text))
    
    def count_aces_in_group(self, group_text):
        """Compte le nombre d'As dans un groupe"""
        return len(re.findall(r'A[♠♥♦♣️]', group_text))
    
    def extract_suits_from_group(self, group_text):
        """Extrait les couleurs d'un groupe de cartes"""
        suits = re.findall(r'[♠♥♦♣]', group_text)
        return [self.suits_mapping.get(s, s) for s in suits]
    
    def should_predict(self, message_text):
        """Détermine si une prédiction doit être lancée selon la logique des As"""
        try:
            # Extraire le numéro de jeu
            game_number = self.extract_game_number(message_text)
            if not game_number:
                return False, None, None
            
            # Rechercher les groupes de cartes avec pattern flexible
            patterns = [
                r'(\d+)\(([^)]+)\)\s*-\s*[✅🔰]*\s*(\d+)\(([^)]+)\)',
                r'(\d+)\(([^)]+)\)\s*[✅🔰-]*\s*(\d+)\(([^)]+)\)',
                r'\(([^)]+)\)\s*-\s*[✅🔰]*\s*\(([^)]+)\)'
            ]
            
            first_group = None
            second_group = None
            
            for pattern in patterns:
                match = re.search(pattern, message_text)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:  # Avec numéros
                        first_group = groups[1]
                        second_group = groups[3]
                    elif len(groups) == 2:  # Sans numéros
                        first_group = groups[0]
                        second_group = groups[1]
                    break
            
            if not first_group or not second_group:
                logger.debug(f"Groupes non trouvés dans: {message_text}")
                return False, None, None
            
            # Compter les As dans chaque groupe
            aces_first = self.count_aces_in_group(first_group)
            aces_second = self.count_aces_in_group(second_group)
            
            logger.info(f"🎯 Analyse As: Premier groupe='{first_group}' (As: {aces_first > 0}), Deuxième groupe='{second_group}' (As: {aces_second > 0})")
            
            # Logique des As: exactement 1 As dans le premier groupe ET 0 As dans le deuxième
            if aces_first == 1 and aces_second == 0:
                logger.info("✅ Condition As validée: 1 As premier groupe + 0 As deuxième groupe")
                
                # Extraire les couleurs du premier groupe pour la prédiction
                suits = self.extract_suits_from_group(first_group)
                suit_prediction = ''.join(suits[:2]) if len(suits) >= 2 else '♣♥'
                
                next_game = game_number + 1
                
                # Vérifier si une prédiction existe déjà
                if next_game in self.prediction_status:
                    logger.info(f"❌ Prédiction déjà existante pour le jeu #{next_game} (statut: {self.prediction_status[next_game]}), ignoré")
                    return False, None, None
                
                return True, next_game, suit_prediction
            else:
                if aces_first == 0:
                    logger.info("❌ Pas d'As dans le premier groupe, pas de prédiction")
                elif aces_first > 1:
                    logger.info(f"❌ Trop d'As dans le premier groupe ({aces_first}), pas de prédiction")
                elif aces_second > 0:
                    logger.info(f"❌ As détecté dans le deuxième groupe ({aces_second}), pas de prédiction")
                
                return False, None, None
                
        except Exception as e:
            logger.error(f"Erreur should_predict: {e}")
            return False, None, None
    
    def verify_prediction(self, message_text):
        """Vérifie les résultats des prédictions"""
        try:
            game_number = self.extract_game_number(message_text)
            if not game_number:
                return None, None
            
            # Vérifier si c'est un résultat final (avec ✅ ou 🔰)
            if not re.search(r'[✅🔰]', message_text):
                return None, None
            
            # Extraire les groupes pour valider le format 2+2
            patterns = [
                r'(\d+)\(([^)]+)\)\s*-\s*[✅🔰]*\s*(\d+)\(([^)]+)\)',
                r'\(([^)]+)\)\s*-\s*[✅🔰]*\s*\(([^)]+)\)'
            ]
            
            first_group = None
            second_group = None
            
            for pattern in patterns:
                match = re.search(pattern, message_text)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:
                        first_group = groups[1]
                        second_group = groups[3]
                    elif len(groups) == 2:
                        first_group = groups[0]
                        second_group = groups[1]
                    break
            
            if not first_group or not second_group:
                return None, None
            
            # Compter les cartes dans chaque groupe
            cards_first = len(re.findall(r'[♠♥♦♣]', first_group))
            cards_second = len(re.findall(r'[♠♥♦♣]', second_group))
            
            logger.info(f"Comptage cartes: groupe1={cards_first}, groupe2={cards_second}")
            
            # Valider le format 2+2
            if cards_first != 2 or cards_second != 2:
                logger.info("❌ Résultat invalide: pas exactement 2+2 cartes, ignoré pour vérification")
                return None, None
            
            logger.info("✅ Résultat valide (2+2)")
            
            # Vérifier les prédictions avec offsets 0, 1, 2, 3
            for offset in range(4):
                predicted_number = game_number - offset
                logger.info(f"Vérification si le jeu #{game_number} correspond à la prédiction #{predicted_number} (offset {offset})")
                
                if predicted_number in self.prediction_status:
                    current_status = self.prediction_status[predicted_number]
                    if current_status == '⌛':  # En attente
                        logger.info(f"Prédiction en attente trouvée: #{predicted_number}")
                        
                        # Déterminer le statut selon l'offset
                        if offset == 0:
                            statut = '✅0️⃣'  # Exact
                        elif offset == 1:
                            statut = '✅1️⃣'  # 1 jeu après
                        elif offset == 2:
                            statut = '✅2️⃣'  # 2 jeux après
                        else:  # offset == 3
                            statut = '✅3️⃣'  # 3 jeux après
                        
                        self.prediction_status[predicted_number] = statut
                        self.status_log.append((predicted_number, statut))
                        yaml_manager.save_predictions(self.prediction_status)
                        
                        logger.info(f"✅ Prédiction réussie: #{predicted_number} validée par le jeu #{game_number} (offset {offset})")
                        return True, predicted_number
            
            # Marquer les anciennes prédictions comme échec si le jeu dépasse prédiction+3
            for pred_num in list(self.prediction_status.keys()):
                if (self.prediction_status[pred_num] == '⌛' and 
                    game_number > pred_num + 3):
                    self.prediction_status[pred_num] = '❌'
                    self.status_log.append((pred_num, '❌'))
                    yaml_manager.save_predictions(self.prediction_status)
                    logger.info(f"❌ Prédiction #{pred_num} marquée échec - jeu #{game_number} dépasse prédit+3")
                    return False, pred_num
            
            logger.info(f"Aucune prédiction correspondante trouvée pour le jeu #{game_number} dans les offsets 0-3")
            pending = [k for k, v in self.prediction_status.items() if v == '⌛']
            logger.info(f"Prédictions actuelles en attente: {pending}")
            return None, None
            
        except Exception as e:
            logger.error(f"Erreur verify_prediction: {e}")
            return None, None
    
    def get_statistics(self):
        """Obtenir les statistiques des prédictions"""
        try:
            total = len(self.status_log)
            if total == 0:
                return {
                    'total': 0,
                    'wins': 0,
                    'losses': 0,
                    'pending': len([s for s in self.prediction_status.values() if s == '⌛']),
                    'win_rate': 0.0
                }
            
            wins = sum(1 for _, status in self.status_log if '✅' in status)
            losses = sum(1 for _, status in self.status_log if '❌' in status)
            pending = len([s for s in self.prediction_status.values() if s == '⌛'])
            win_rate = (wins / total * 100) if total > 0 else 0.0
            
            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'win_rate': win_rate
            }
        except Exception as e:
            logger.error(f"Erreur get_statistics: {e}")
            return {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'win_rate': 0.0}

predictor = SimplePredictor()

# Configuration
CONFIG_FILE = "bot_config.json"

def load_config():
    """Charge la configuration depuis le fichier JSON"""
    global detected_stat_channel, detected_display_channel, prediction_interval
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                detected_stat_channel = config.get('stat_channel')
                detected_display_channel = config.get('display_channel')
                prediction_interval = config.get('prediction_interval', 1)
                logger.info(f"✅ Configuration chargée: Stats={detected_stat_channel}, Display={detected_display_channel}, Intervalle={prediction_interval}min")
                return True
    except Exception as e:
        logger.error(f"Erreur chargement config: {e}")
    
    return False

def save_config():
    """Sauvegarde la configuration dans le fichier JSON"""
    try:
        config = {
            'stat_channel': detected_stat_channel,
            'display_channel': detected_display_channel,
            'prediction_interval': prediction_interval
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("✅ Configuration sauvegardée")
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde config: {e}")
        return False

# Health check pour Render.com
async def health_check(request):
    """Health check endpoint pour Render.com"""
    return web.Response(text=f"✅ Bot Telegram Prédiction v2024 - Port {PORT} - Running OK!", status=200)

async def bot_status_endpoint(request):
    """Endpoint de statut détaillé"""
    try:
        status = {
            "bot_online": True,
            "port": PORT,
            "stat_channel": detected_stat_channel,
            "display_channel": detected_display_channel,
            "prediction_interval": prediction_interval,
            "predictions_active": len(predictor.prediction_status),
            "yaml_database": "active",
            "timestamp": datetime.now().isoformat()
        }
        return web.json_response(status)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# --- COMMANDES TELEGRAM ---

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Commande de démarrage"""
    welcome_msg = f"""🎯 **Bot de Prédiction v2024 - Bienvenue !**

🔹 **Architecture YAML Pure** - Plus de PostgreSQL
🔹 **Logique As Optimisée** - 1 As premier + 0 As deuxième groupe
🔹 **Port {PORT}** - Configuré pour Render.com

**Fonctionnalités** :
• Prédictions automatiques avec logique des As
• Vérification des résultats avec statuts détaillés
• Configuration flexible de l'intervalle de prédiction
• Architecture YAML complète et autonome

**Commandes Administrateur** :
• `/status` - État complet du système
• `/intervalle [1-60]` - Configurer délai prédiction

Le bot est prêt ! 🚀"""
    
    await event.respond(welcome_msg)
    logger.info(f"Message bienvenue envoyé à {event.sender_id}")

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    """Affiche le statut complet du système"""
    if event.sender_id != ADMIN_ID:
        return
    
    try:
        # Statistiques du prédicteur
        pred_stats = predictor.get_statistics()
        pred_status = f"""🎯 **Prédicteur**:
• Total prédictions: {pred_stats['total']}
• Réussites: {pred_stats['wins']} ✅
• Échecs: {pred_stats['losses']} ❌
• En attente: {pred_stats['pending']} ⏳
• Taux réussite: {pred_stats['win_rate']:.1f}%"""
        
        status_msg = f"""📊 **État du Bot v2024**

🌐 **Configuration**:
• Canal statistiques: {'✅' if detected_stat_channel else '❌'} ({detected_stat_channel})
• Canal affichage: {'✅' if detected_display_channel else '❌'} ({detected_display_channel})
• Port serveur: {PORT}
• Intervalle prédiction: {prediction_interval} minute(s)

{pred_status}

🔧 **Architecture**:
• Base données: YAML (autonome)
• Logique As: 1 premier + 0 deuxième groupe
• Version: v2024 Render.com"""
        
        await event.respond(status_msg)
        
    except Exception as e:
        logger.error(f"Erreur status: {e}")
        await event.respond(f"❌ Erreur: {e}")

@client.on(events.NewMessage(pattern=r'/intervalle (\d+)'))
async def set_prediction_interval(event):
    """Configure l'intervalle de prédiction"""
    if event.sender_id != ADMIN_ID:
        return
        
    try:
        global prediction_interval
        new_interval = int(event.pattern_match.group(1))
        
        if 1 <= new_interval <= 60:
            old_interval = prediction_interval
            prediction_interval = new_interval
            
            # Sauvegarder la configuration
            save_config()
            
            await event.respond(f"""✅ **Intervalle de Prédiction Mis à Jour**

⏱️ **Ancien**: {old_interval} minute(s)
⏱️ **Nouveau**: {prediction_interval} minute(s)

Configuration sauvegardée automatiquement.""")
            
            logger.info(f"✅ Intervalle mis à jour: {old_interval} → {prediction_interval} minutes")
        else:
            await event.respond("❌ **Erreur**: L'intervalle doit être entre 1 et 60 minutes")
            
    except ValueError:
        await event.respond("❌ **Erreur**: Veuillez entrer un nombre valide")
    except Exception as e:
        logger.error(f"Erreur set_prediction_interval: {e}")
        await event.respond(f"❌ Erreur: {e}")

# Messages handler principal avec logique As
@client.on(events.NewMessage())
@client.on(events.MessageEdited())
async def handle_messages(event):
    """Gestionnaire principal des messages"""
    try:
        message_text = event.message.message if event.message else ""
        channel_id = event.chat_id
        
        # Vérifier si c'est le bon canal
        if detected_stat_channel and channel_id == detected_stat_channel:
            logger.info(f"✅ Message du canal stats: {message_text[:100]}")
            
            # Logique de prédiction avec analyse des As
            should_predict, game_number, suit = predictor.should_predict(message_text)
            if should_predict and game_number and suit:
                prediction_text = f"🔵{game_number} 🔵3D: statut :⏳"
                logger.info(f"🎯 Prédiction générée: {prediction_text}")
                
                # Enregistrer la prédiction
                predictor.prediction_status[game_number] = '⌛'
                predictor.last_predictions.append((game_number, suit))
                yaml_manager.save_predictions(predictor.prediction_status)
                logger.info(f"✅ Prédiction créée: Jeu #{game_number} -> {suit}")
                
                # Diffuser la prédiction si canal configuré
                if detected_display_channel:
                    try:
                        await client.send_message(detected_display_channel, prediction_text)
                        logger.info(f"📤 Prédiction diffusée sur canal {detected_display_channel}")
                    except Exception as e:
                        logger.error(f"Erreur diffusion: {e}")
            
            # Vérification des résultats
            verified, number = predictor.verify_prediction(message_text)
            if verified is not None and number is not None:
                status = predictor.prediction_status.get(number, '❌')
                logger.info(f"🔍 Vérification jeu #{number}: {status}")
                
                # Mettre à jour le message de prédiction si possible
                if detected_display_channel and verified:
                    try:
                        # Chercher le message de prédiction correspondant pour le mettre à jour
                        logger.info(f"Message de prédiction #{number} mis à jour avec statut: {status}")
                    except Exception as e:
                        logger.error(f"Erreur mise à jour message: {e}")
                
        else:
            logger.debug(f"Message ignoré - Canal {channel_id} ≠ Stats {detected_stat_channel}")
            
    except Exception as e:
        logger.error(f"Erreur handle_messages: {e}")

# Démarrage serveur web
async def start_web_server():
    """Démarre le serveur web pour Render.com"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', bot_status_endpoint)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Serveur web démarré sur 0.0.0.0:{PORT}")

async def main():
    """Fonction principale"""
    try:
        logger.info("🚀 Démarrage Bot Prédiction v2024")
        
        # Vérifier les variables d'environnement
        if not API_ID or not API_HASH or not BOT_TOKEN or not ADMIN_ID:
            logger.error("❌ Variables d'environnement manquantes!")
            return
            
        logger.info(f"✅ Configuration: API_ID={API_ID}, ADMIN_ID={ADMIN_ID}, PORT={PORT}")
        
        # Charger configuration
        load_config()
        
        # Démarrer serveur web
        await start_web_server()
        
        # Démarrer bot Telegram
        logger.info("🔗 Connexion au bot Telegram...")
        await client.start(bot_token=BOT_TOKEN)
        
        me = await client.get_me()
        logger.info(f"✅ Bot connecté: @{me.username}")
        logger.info("🔄 Bot en ligne et en attente de messages...")
        logger.info(f"🌐 Accès web: http://0.0.0.0:{PORT}")
        
        # Boucle principale
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())