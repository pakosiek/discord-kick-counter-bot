import discord
from discord.ext import commands
import json
import asyncio
import os
import datetime
from dotenv import load_dotenv
load_dotenv() # Wczytuje zmienne z pliku .env

# --- Konfiguracja ---
TOKEN = os.environ.get('TOKEN')
LOG_CHANNEL_ID = 1429220965690114189  # Pana ID kanału
NAZWA_PLIKU_STATYSTYK = "kick_stats.json"

# --- Konfiguracja Intencji (Intents) ---
intents = discord.Intents.default()
intents.voice_states = True      # Do śledzenia kanałów głosowych
intents.guilds = True            # Do Dziennika Zdarzeń
intents.members = True           # Do pobierania listy członków
intents.message_content = True   # Do komend !staty, !top

# --- Zmienne Globalne ---
# Słownik do śledzenia "zużycia" logów (dla grupowych wyrzuceń)
PROCESSED_LOG_COUNTS = {}

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Funkcje Pomocnicze do Bazy Danych (JSON) ---

def load_stats():
    """Wczytuje statystyki z pliku JSON."""
    if not os.path.exists(NAZWA_PLIKU_STATYSTYK):
        return {}
    try:
        with open(NAZWA_PLIKU_STATYSTYK, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_stats(data):
    """Zapisuje statystyki do pliku JSON."""
    with open(NAZWA_PLIKU_STATYSTYK, 'w') as f:
        json.dump(data, f, indent=4)

#
# ZASTĄP TĘ FUNKCJĘ
#
async def zarejestruj_wyrzucenie(kicker, kicked, channel, is_nuke=False, is_first_nuke_victim=False):
    """
    Funkcja pomocnicza do zapisu statystyk i wysyłania logu.
    Teraz obsługuje 'is_nuke' oraz 'is_first_nuke_victim' do liczenia zdarzeń.
    """
    
    # --- 1. Ustawienie tytułu i koloru wiadomości ---
    if is_nuke:
        title = "💥 WYKRYTO KASACJĘ KANAŁU (NUKE) 💥"
        color = discord.Color.dark_red()
        print(f"--- [SUKCES] Znaleziono 'Nuke': {kicker.name} wyrzucił {kicked.name} (przez kasację kanału).")
    else:
        title = "👢 Wykryto Wyrzucenie z Kanału Głosowego"
        color = discord.Color.red()
        print(f"--- [SUKCES] Znaleziono pasujący wpis: {kicker.name} wyrzucił {kicked.name} ---")

    # --- 2. Wysłanie powiadomienia na kanał logów ---
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        try:
            embed = discord.Embed(
                title=title,
                color=color,
                description=f"**Wyrzucający:** {kicker.mention} (`{kicker.name}`)\n"
                            f"**Wyrzucony:** {kicked.mention} (`{kicked.name}`)\n"
                            f"**Z kanału:** `{channel.name}`"
            )
            embed.set_thumbnail(url=kicker.display_avatar.url)
            embed.set_footer(text=f"ID Wyrzucającego: {kicker.id}")
            await log_channel.send(embed=embed)
            print("--- Wiadomość na kanał logów wysłana pomyślnie.")
        except discord.Forbidden:
            print(f"!!! BŁĄD: Bot nie ma uprawnień do WYSYŁANIA WIADOMOŚCI na kanale logów.")
        except Exception as e:
            print(f"!!! BŁĄD: Nie udało się wysłać wiadomości na kanał logów: {e}")
    else:
        print(f"!!! BŁĄD: Nie znaleziono kanału logów (ID: {LOG_CHANNEL_ID}).")

    # --- 3. Zapis do pliku JSON (NOWA STRUKTURA) ---
    print("--- Zapisuję statystyki do pliku JSON...")
    stats = load_stats()
    kicker_id_str = str(kicker.id)
    kicked_id_str = str(kicked.id)

    # Upewnij się, że podstawowa struktura istnieje
    if kicker_id_str not in stats:
        stats[kicker_id_str] = {"regular_kicks": {}, "nuke_kicks": {}, "nuke_events_count": 0}
    if "regular_kicks" not in stats[kicker_id_str]:
        stats[kicker_id_str]["regular_kicks"] = {}
    if "nuke_kicks" not in stats[kicker_id_str]:
        stats[kicker_id_str]["nuke_kicks"] = {}
    if "nuke_events_count" not in stats[kicker_id_str]:
        stats[kicker_id_str]["nuke_events_count"] = 0
    
    if is_nuke:
        # Zapisz ofiarę 'nuke_kick'
        if kicked_id_str not in stats[kicker_id_str]["nuke_kicks"]:
            stats[kicker_id_str]["nuke_kicks"][kicked_id_str] = 0
        stats[kicker_id_str]["nuke_kicks"][kicked_id_str] += 1
        print(f"  [DEBUG] Zapisano jako NUKE (ofiara).")
        
        # NOWA CZĘŚĆ: Zapisz 'nuke_event', jeśli to pierwsza ofiara z tego logu
        if is_first_nuke_victim:
            stats[kicker_id_str]["nuke_events_count"] += 1
            print(f"  [DEBUG] To pierwsza ofiara tego nuke'a. Zwiększono nuke_events_count.")
    else:
        # Zapisz jako 'regular_kick'
        if kicked_id_str not in stats[kicker_id_str]["regular_kicks"]:
            stats[kicker_id_str]["regular_kicks"][kicked_id_str] = 0
        stats[kicker_id_str]["regular_kicks"][kicked_id_str] += 1
        print(f"  [DEBUG] Zapisano jako REGULARNY KICK.")
    
    save_stats(stats)
    print("--- Statystyki zapisane.")
    print("="*40 + "\n")
# --- Logika Bota ---

@bot.event
async def on_ready():
    """Wydarzenie uruchamiane po pomyślnym połączeniu bota."""
    print(f'Zalogowano jako: {bot.user}')
    
    if LOG_CHANNEL_ID == 0:
        print("!!! OSTRZEŻENIE: LOG_CHANNEL_ID nie zostało ustawione! Bot nie będzie wysyłał logów na kanał.")
    else:
        print(f"Bot będzie logował wyrzucenia na kanale o ID: {LOG_CHANNEL_ID}")
        
    print("\nTrwa pobieranie listy członków serwera (cache'owanie)...")
    try:
        for guild in bot.guilds:
            print(f"Pobieram członków dla serwera: {guild.name}...")
            await guild.chunk() 
            print(f"Pobrano członków dla {guild.name}.")
        print("--- Pobieranie członków zakończone. Bot jest w pełni gotowy. ---\n")
    except Exception as e:
        print(f"!!! Nie udało się pobrać członków: {e}")


#
# ZASTĄP CAŁĄ FUNKCJĘ on_voice_state_update TYM KODEM
#
#
# ZASTĄP TĘ FUNKCJĘ
#
#
# ZASTĄP CAŁĄ FUNKCJĘ on_voice_state_update TYM KODEM
#
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """
    Uruchamia się, gdy ktoś opuści kanał głosowy.
    Sprawdza, czy to był 'Nuke', czy 'Kick'.
    """
    
    # Uruchom logikę tylko wtedy, gdy ktoś OPUŚCIŁ kanał
    if before.channel and not after.channel:
        
        print("\n" + "="*40)
        print(f"--- [KROK 1] WYKRYTO WYJŚCIE UŻYTKOWNIKA ---")
        print(f"Użytkownik: {member.name} (ID: {member.id})")
        print(f"Opuścił kanał: {before.channel.name} (ID: {before.channel.id})")
        
        await asyncio.sleep(2.5) 
        guild = member.guild
        now = datetime.datetime.now(datetime.timezone.utc)

        # --- LOGIKA v7.3 (POPRAWIONA): NAJPIERW SPRAWDŹ CZY TO "NUKE" ---
        try:
            print(f"--- [KROK 2] Sprawdzam, czy to był 'Nuke'...")
            
            async for entry in guild.audit_logs(
                limit=5, 
                action=discord.AuditLogAction.channel_delete
            ):
                
                time_difference = abs((now - entry.created_at).total_seconds())
                
                if entry.target is None:
                    print(f"  [DEBUG Nuke Check] Znalazłem log usunięcia, ale 'target' jest PUSTY (None). Ignoruję.")
                    continue
                    
                target_channel_id = entry.target.id 
                print(f"  [DEBUG Nuke Check] Znalazłem log usunięcia kanału. ID celu: {target_channel_id}, Wiek: {time_difference:.1f}s")

                if target_channel_id == before.channel.id and time_difference < 30.0:
                    nuker = entry.user
                    
                    # --- POPRAWKA: Sprawdzenie samobójczego "Nuke'a" ---
                    if nuker == member:
                        print(f"--- WNIOSEK: Użytkownik sam usunął kanał, na którym był. Ignoruję (samobójczy 'Nuke').")
                        print("="*40 + "\n")
                        return # Ignoruje i kończy
                    # --- KONIEC POPRAWKI ---
                    
                    current_nuke_uses = PROCESSED_LOG_COUNTS.get(entry.id, 0)
                    is_first = (current_nuke_uses == 0)
                    PROCESSED_LOG_COUNTS[entry.id] = current_nuke_uses + 1
                    
                    if is_first:
                        print(f"--- [KROK 3] To był 'Nuke'! To PIERWSZA ofiara z tego logu.")
                    else:
                        print(f"--- [KROK 3] To był 'Nuke'! To KOLEJNA ofiara z tego logu (użycie nr {current_nuke_uses + 1}).")
                    
                    print(f"--- Winowajca (Nuker): {nuker.name} (ID: {nuker.id})")
                    
                    await zarejestruj_wyrzucenie(nuker, member, before.channel, is_nuke=True, is_first_nuke_victim=is_first)
                    return
            
            print(f"--- [KROK 2b] To nie był 'Nuke'. Sprawdzam zwykłe wyrzucenia...")

        except discord.Forbidden:
            print("!!! BŁĄD KRYTYCZNY: Bot nie ma uprawnienia 'Przeglądanie dziennika zdarzeń' (przy sprawdzaniu Nuke).")
        except Exception as e:
            print(f"!!! Wystąpił nieoczekiwany błąd (Nuke Check): {e}")
        
        # --- KONIEC LOGIKI "NUKE" ---

        # --- LOGIKA DLA ZWYKŁYCH WYRZUCEŃ (jeśli to nie był Nuke) ---
        try:
            async for entry in member.guild.audit_logs(
                limit=10, 
                action=discord.AuditLogAction.member_disconnect
            ):
                
                kicker = entry.user
                target = entry.target
                time_difference = abs((now - entry.created_at).total_seconds()) 
                
                if target == member:
                    if kicker == member:
                        print(f"--- WNIOSEK: Samorozłączenie (log pełny). Ignoruję.")
                        print("="*40 + "\n")
                        return 
                    print(f"--- [KROK 3] Znaleziono IDEALNE dopasowanie.")
                    await zarejestruj_wyrzucenie(kicker, member, before.channel, is_nuke=False, is_first_nuke_victim=False)
                    return

                if target is None and time_difference < 45.0:
                    total_kicks_in_log = getattr(entry.extra, 'count', 1)
                    current_uses = PROCESSED_LOG_COUNTS.get(entry.id, 0)
                    
                    if current_uses >= total_kicks_in_log:
                        print(f"  [DEBUG Kick Check] Log od {kicker.name} (Wiek: {time_difference:.1f}s) jest już W PEŁNI UŻYTY. Szukam dalej...")
                        continue 

                    if kicker == member:
                        print(f"--- WNIOSEK: Samorozłączenie (log pusty). Ignoruję.")
                        print("="*40 + "\n")
                        return

                    print(f"--- [KROK 3] Znaleziono PUSTY, ŚWIEŻY i DOSTĘPNY log (stworzony {time_difference:.1f}s temu).")
                    print(f"--- ZAKŁADAM, że to '{kicker.name}' wyrzucił '{member.name}'.")
                    PROCESSED_LOG_COUNTS[entry.id] = current_uses + 1
                    await zarejestruj_wyrzucenie(kicker, member, before.channel, is_nuke=False, is_first_nuke_victim=False)
                    return 
            
            print(f"--- [KROK 3] BŁĄD: Pętla zakończona. NIE znaleziono pasującego wpisu dla {member.name}.")
            print(f"--- Wniosek: Użytkownik wyszedł sam.")
            print("="*40 + "\n")

        except discord.Forbidden:
            print(f"!!! BŁĄD KRYTYCZNY: Bot nie ma uprawnienia 'Przeglądanie dziennika zdarzeń' (Kick). ---")
        except Exception as e:
            print(f"!!! Wystąpił nieoczekiwany błąd (Kick Check): {e} ---")

#
# KONIEC KODU DO SKOPIOWANIA
#

# --- Komendy do Wyświetlania Statystyk ---

#
# ZASTĄP TĘ KOMENDĘ
#
#
# ZASTĄP CAŁĄ FUNKCJĘ (KOMENDĘ) !staty TYM KODEM
#
@bot.command(name='staty')
async def staty(ctx, member: discord.Member):
    """Wyświetla szczegółowe statystyki wyrzuceń dla danego użytkownika."""
    stats = load_stats()
    member_id_str = str(member.id)
    
    embed = discord.Embed(
        title=f"Statystyki dla {member.display_name}",
        color=member.color
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # --- 1. Kogo wyrzucił (zwykłe) ---
    kicked_others_str = ""
    regular_kicks = stats.get(member_id_str, {}).get("regular_kicks", {})
    
    if regular_kicks:
        total_regular_kicks = sum(regular_kicks.values())
        kicked_others_str = f"Łącznie **{total_regular_kicks}** osób.\n"
        
        sorted_kicked = sorted(regular_kicks.items(), key=lambda item: item[1], reverse=True)
        # Pokaż top 5 ofiar, żeby nie spamować
        for kicked_id, count in sorted_kicked[:5]:
            try:
                kicked_user = await bot.fetch_user(int(kicked_id))
                kicked_others_str += f"• w tym **{kicked_user.name}**: {count} raz(y)\n"
            except discord.NotFound:
                kicked_others_str += f"• w tym *[Nieznany Użytkownik {kicked_id}]*: {count} raz(y)\n"
    else:
        kicked_others_str = "Jeszcze nikogo nie wyrzucił."

    embed.add_field(name="Wyrzucił (zwykłe):", value=kicked_others_str, inline=False)
    
    # --- 2. Kogo wyrzucił (Nuke) ---
    nuke_kicks_data = stats.get(member_id_str, {}).get("nuke_kicks", {})
    nuke_events_count = stats.get(member_id_str, {}).get("nuke_events_count", 0)
    nuke_str = ""
    
    total_nuke_victims = sum(nuke_kicks_data.values()) # Liczba ofiar
    
    if total_nuke_victims > 0:
        # NOWA, BARDZIEJ SZCZEGÓŁOWA WERSJA
        nuke_str = (
            f"**{nuke_events_count}** raz(y) usunął kanał, "
            f"wyrzucając łącznie **{total_nuke_victims}** osób.\n"
        )
        
        # Sortujemy ofiary "Nuke'a"
        sorted_nukes = sorted(nuke_kicks_data.items(), key=lambda item: item[1], reverse=True)
        
        # Pokaż top 5 ofiar, żeby nie spamować
        for kicked_id, count in sorted_nukes[:5]:
            try:
                kicked_user = await bot.fetch_user(int(kicked_id))
                nuke_str += f"• w tym **{kicked_user.name}**: {count} raz(y)\n"
            except discord.NotFound:
                nuke_str += f"• w tym *[Nieznany Użytkownik {kicked_id}]*: {count} raz(y)\n"
        
        if len(sorted_nukes) > 5:
            nuke_str += f"...i {len(sorted_nukes) - 5} innych."
            
    else:
        nuke_str = "Jeszcze nikogo nie 'zbukował'."

    embed.add_field(name="Wyrzucił (przez 'Nuke'):", value=nuke_str, inline=False)
    
    # --- 3. Kto go wyrzucił (zwykłe i nuke) ---
    was_kicked_by_str = ""
    kickers_list = []
    
    for kicker_id, data in stats.items():
        reg_targets = data.get("regular_kicks", {})
        if member_id_str in reg_targets:
            count = reg_targets[member_id_str]
            try:
                kicker_user = await bot.fetch_user(int(kicker_id))
                kickers_list.append((f"**{kicker_user.name}**", count, ""))
            except discord.NotFound:
                kickers_list.append((f"*[Nieznany Użytkownik {kicker_id}]*", count, ""))
        
        nuke_targets = data.get("nuke_kicks", {})
        if member_id_str in nuke_targets:
            count = nuke_targets[member_id_str]
            try:
                kicker_user = await bot.fetch_user(int(kicker_id))
                kickers_list.append((f"**{kicker_user.name}**", count, " (przez 'Nuke')"))
            except discord.NotFound:
                kickers_list.append((f"*[Nieznany Użytkownik {kicked_id}]*", count, " (przez 'Nuke')"))
    
    if kickers_list:
        sorted_kickers = sorted(kickers_list, key=lambda item: item[1], reverse=True)
        for name, count, tag in sorted_kickers:
            was_kicked_by_str += f"• {name}: {count} raz(y){tag}\n"
    else:
        was_kicked_by_str = "Jeszcze nikt go nie wyrzucił."

    embed.add_field(name="Został wyrzucony przez:", value=was_kicked_by_str, inline=False)
    
    await ctx.send(embed=embed)

#
# KONIEC KODU DO SKOPIOWANIA
#

#
# ZASTĄP TĘ KOMENDĘ
#
@bot.command(name='top')
async def top(ctx):
    """Wyświetla top 3 osoby, które najwięcej wyrzucały (łącznie zwykłe + nuke)."""
    stats = load_stats()
    
    if not stats:
        await ctx.send("Brak statystyk do wyświetlenia.")
        return
        
    total_kicks = {}
    for kicker_id, data in stats.items():
        reg_total = sum(data.get("regular_kicks", {}).values())
        nuke_total = sum(data.get("nuke_kicks", {}).values())
        total_kicks[kicker_id] = reg_total + nuke_total
        
    sorted_kicks = sorted(total_kicks.items(), key=lambda item: item[1], reverse=True)
    
    embed = discord.Embed(
        title="Top 3 Wyrzucających 🏆 (Łącznie)",
        color=discord.Color.gold()
    )
    
    description = ""
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (kicker_id, count) in enumerate(sorted_kicks[:3]):
        if count == 0: continue
        try:
            user = await bot.fetch_user(int(kicker_id))
            # Pobieramy szczegółowe dane do nowego formatu
            reg_total = sum(stats.get(kicker_id, {}).get("regular_kicks", {}).values())
            nuke_victims_total = sum(stats.get(kicker_id, {}).get("nuke_kicks", {}).values())
            nuke_events_total = stats.get(kicker_id, {}).get("nuke_events_count", 0)
            
            # NOWY FORMAT OPISU
            description += (
                f"{medals[i]} **{user.name}** - {count} łącznie\n"
                f"    (👢{reg_total} zwykłych | 💥{nuke_victims_total} ofiar z {nuke_events_total} 'nuke'ów')\n"
            )
        except discord.NotFound:
            description += f"{medals[i]} *[Nieznany Użytkownik {kicker_id}]* - {count} łącznie\n"
            
    if not description:
        description = "Brak wyrzuceń na serwerze."
        
    embed.description = description
    await ctx.send(embed=embed)


# --- Uruchomienie Bota ---
if __name__ == "__main__":
    if TOKEN == "TUTAJ_WKLEJ_SWOJ_NOWY_TOKEN_BOTA":
        print("BŁĄD: Musisz wkleić swój token bota w zmiennej TOKEN na górze pliku!")
    elif LOG_CHANNEL_ID == 0:
        print("!!! OSTRZEŻENIE: Nie ustawiłeś LOG_CHANNEL_ID. Bot uruchomi się, ale nie będzie wysyłał logów na kanał.")
        bot.run(TOKEN)
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "="*50)
            print("BŁĄD KRYTYCZNY: Brak Intencji (Intents).")
            print("Bot nie mógł się uruchomić, ponieważ nie włączyłeś")
            print("wymaganych 'Privileged Gateway Intents' w Panelu Deweloperskim Discord.")
            print("\nUpewnij się, że WSZYSTKIE 3 intencje są WŁĄCZONE:")
            print("1. PRESENCE INTENT")
            print("2. SERVER MEMBERS INTENT")
            print("3. MESSAGE CONTENT INTENT")
            print("="*50)
        except discord.errors.LoginFailure:
            print("\n" + "="*50)
            print("BŁĄD KRYTYCZNY: Nieprawidłowy Token.")
            print("Bot nie mógł się zalogować. Sprawdź, czy")
            print("poprawnie wkleiłeś swój NOWY token.")
            print("="*50)